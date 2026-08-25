import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import numpy as np
import structlog

from app.application.ports.frame_source import IFrameSource
from app.domain.entities.frame import Frame
from app.domain.exceptions import FrameSourceUnavailableError

logger = structlog.get_logger(__name__)

_BYTES_PER_PIXEL = 3  # bgr24, matching every other Frame.image in this codebase (cv2 default)
_TERMINATE_TIMEOUT_SECONDS = 5.0
_KILL_TIMEOUT_SECONDS = 3.0


def _parse_resolution(resolution: str) -> tuple[int, int]:
    width_str, _, height_str = resolution.partition("x")
    return int(width_str), int(height_str)


class RtmpFrameSource(IFrameSource):
    """Connects to the RTMP demo server via a system `ffmpeg` subprocess piping raw frames on
    its stdout, rather than `cv2.VideoCapture`'s bundled FFmpeg (docs/RTMP_DEMO.md,
    docs/TECHNICAL_DECISIONS.md TD-33's "observed caveat").

    `opencv-python-headless` bundles an older FFmpeg build (avformat 61.x)
    than the system `ffmpeg` this project already requires for recording
    (TD-22, `ffmpeg_binary_path`) — its RTMP demuxer was observed
    periodically losing chunk-stream sync against MediaMTX
    (`RTMP packet size mismatch`, `frame stream ended unexpectedly`,
    recurring every few seconds), which the newer system `ffmpeg` binary
    consuming the identical stream did not exhibit in the same manual
    testing. This class trades `cv2.VideoCapture`'s convenience for that
    reliability: `ffmpeg -i <rtmp_url> -f rawvideo -pix_fmt bgr24 pipe:1`,
    parsed as fixed-size chunks — fixed-size only works because both ends of
    this demo's RTMP pipeline agree on resolution via the same
    `Settings.rtmp_publish_resolution` value the publisher encodes at
    (`FfmpegRtmpPublisher`), so this consumer's `-s` output option always
    matches what's actually arriving and every frame is exactly
    `width * height * 3` bytes.

    `start()` blocks until the *first* frame is actually read (bounded by
    `open_timeout_seconds`) before returning — the same "confirmed open, not
    just spawned" guarantee `cv2.VideoCapture.isOpened()` gives every other
    `IFrameSource` in this codebase, so `ReconnectSupervisor`'s "state
    becomes CONNECTED right after `start()` succeeds" assumption
    (`reconnect_supervisor.py`) still holds. Every subsequent read in
    `frames()` is bounded by `read_timeout_seconds`, so a stalled (not
    exited) subprocess is detected and reconnected the same way a dead one
    is, not left blocking forever.

    Never logs `rtmp_url`: it may embed read credentials (TD-15/AGENTS.md).
    ffmpeg's stderr is discarded entirely (`DEVNULL`), same as
    `FfmpegRecordingWorker`/`FfmpegRtmpPublisher` — it can echo the URL in
    its own diagnostic output.
    """

    def __init__(
        self,
        rtmp_url: str,
        source_id: str,
        ffmpeg_binary_path: str,
        resolution: str,
        *,
        open_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 5.0,
    ) -> None:
        self._rtmp_url = rtmp_url
        self._source_id = source_id
        self._ffmpeg_binary_path = ffmpeg_binary_path
        self._width, self._height = _parse_resolution(resolution)
        self._frame_size = self._width * self._height * _BYTES_PER_PIXEL
        self._open_timeout_seconds = open_timeout_seconds
        self._read_timeout_seconds = read_timeout_seconds
        self._process: asyncio.subprocess.Process | None = None
        self._first_frame: bytes | None = None

    @property
    def source_id(self) -> str:
        return self._source_id

    async def start(self) -> None:
        argv = [
            self._ffmpeg_binary_path,
            "-loglevel",
            "error",
            # MediaMTX's RTMP output was observed failing ffmpeg's *default*
            # probe window ("could not find codec parameters", the input
            # closing before a single frame arrived) even though the same
            # stream opens fine once given more time to analyze — MediaMTX's
            # own timestamp handling logs "Negative cts, previous timestamps
            # might be wrong" against this project's publisher, which is
            # consistent with needing a wider probe. 10s/10MB comfortably
            # covers that in testing without materially slowing a normal
            # open (probing ends as soon as enough packets are seen, not
            # after the full duration).
            "-analyzeduration",
            "10000000",
            "-probesize",
            "10000000",
            "-i",
            self._rtmp_url,
            "-an",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self._width}x{self._height}",
            "pipe:1",
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=self._frame_size + 1,
            )
        except OSError as exc:
            raise FrameSourceUnavailableError(
                f"Could not start ffmpeg RTMP consumer for source {self._source_id!r}"
            ) from exc

        assert process.stdout is not None
        try:
            first_frame = await asyncio.wait_for(
                process.stdout.readexactly(self._frame_size), timeout=self._open_timeout_seconds
            )
        except (TimeoutError, asyncio.IncompleteReadError) as exc:
            await self._terminate(process)
            raise FrameSourceUnavailableError(
                f"Could not open RTMP stream for source {self._source_id!r}"
            ) from exc

        self._process = process
        self._first_frame = first_frame

    async def stop(self) -> None:
        process = self._process
        self._process = None
        self._first_frame = None
        if process is not None:
            await self._terminate(process)

    async def frames(self) -> AsyncIterator[Frame]:
        process = self._process
        if process is None or self._first_frame is None:
            raise FrameSourceUnavailableError("start() must succeed before frames() is iterated")
        assert process.stdout is not None

        sequence = 0
        raw: bytes | None = self._first_frame
        self._first_frame = None
        while raw is not None:
            yield Frame(
                source_id=self._source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.frombuffer(raw, dtype=np.uint8)
                .reshape((self._height, self._width, _BYTES_PER_PIXEL))
                .copy(),
            )
            sequence += 1
            try:
                raw = await asyncio.wait_for(
                    process.stdout.readexactly(self._frame_size),
                    timeout=self._read_timeout_seconds,
                )
            except asyncio.IncompleteReadError:
                return
            except TimeoutError as exc:
                raise FrameSourceUnavailableError(
                    f"RTMP consumer for source {self._source_id!r} stalled — "
                    f"no frame within {self._read_timeout_seconds}s"
                ) from exc

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_TIMEOUT_SECONDS)
            except TimeoutError:
                logger.warning("rtmp_demo.consumer_force_kill", pid=process.pid)
                process.kill()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=_KILL_TIMEOUT_SECONDS)
