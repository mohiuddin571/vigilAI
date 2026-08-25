import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import cv2

from app.application.ports.frame_source import IFrameSource
from app.domain.entities.frame import Frame
from app.domain.exceptions import FrameSourceUnavailableError


def _open_capture(url: str, open_timeout_ms: int, read_timeout_ms: int) -> cv2.VideoCapture:
    """Open an RTMP URL via OpenCV's bundled FFmpeg backend — the same `cv2.VideoCapture`/FFmpeg
    decode path `RawRtspFrameSource`/`Mp4FileFrameSource` use (docs/ARCHITECTURE.md §5), just
    pointed at `rtmp://` instead of `rtsp://`/a local file. No RTSP-transport env var here — that
    FFmpeg option is RTSP-specific and doesn't apply to RTMP."""
    return cv2.VideoCapture(
        url,
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            open_timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            read_timeout_ms,
        ],
    )


class RtmpFrameSource(IFrameSource):
    """Connects to the RTMP demo server's RTMP URL and decodes frames from it (docs/RTMP_DEMO.md).

    A trimmed sibling of `RawRtspFrameSource`
    (`infrastructure/streaming/rtsp_frame_source.py`) — same dedicated
    single-worker `ThreadPoolExecutor` per instance, for the same reason
    documented there: `cv2.VideoCapture`'s bundled FFmpeg backend isn't safe
    for a `release()` to race a still-in-flight `read()` from a different OS
    thread. Wrapped by the existing `StreamWorker` unchanged (multiprocessing
    isolation + `ReconnectSupervisor` backoff/retry) exactly like every other
    `IFrameSource` — this is what makes the RTMP Consumer reconnect when the
    publisher hasn't started yet or drops mid-stream (request scenarios
    #5/#6/#7/#8), with no new reconnect logic in this module.

    Never logs `rtmp_url`: it may embed read credentials (TD-15/AGENTS.md).
    """

    def __init__(
        self,
        rtmp_url: str,
        source_id: str,
        *,
        open_timeout_ms: int = 5000,
        read_timeout_ms: int = 5000,
    ) -> None:
        self._rtmp_url = rtmp_url
        self._source_id = source_id
        self._open_timeout_ms = open_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._cap: cv2.VideoCapture | None = None
        self._executor: ThreadPoolExecutor | None = None

    @property
    def source_id(self) -> str:
        return self._source_id

    async def start(self) -> None:
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_running_loop()
        cap = await loop.run_in_executor(
            executor, _open_capture, self._rtmp_url, self._open_timeout_ms, self._read_timeout_ms
        )
        if not cap.isOpened():
            await loop.run_in_executor(executor, cap.release)
            await asyncio.to_thread(executor.shutdown)
            raise FrameSourceUnavailableError(
                f"Could not open RTMP stream for source {self._source_id!r}"
            )
        self._cap = cap
        self._executor = executor

    async def stop(self) -> None:
        if self._cap is not None and self._executor is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._cap.release)
            self._cap = None
        if self._executor is not None:
            executor = self._executor
            self._executor = None
            await asyncio.to_thread(executor.shutdown)

    async def frames(self) -> AsyncIterator[Frame]:
        if self._cap is None or self._executor is None:
            raise FrameSourceUnavailableError("start() must succeed before frames() is iterated")
        cap = self._cap
        executor = self._executor
        loop = asyncio.get_running_loop()
        sequence = 0
        while True:
            ok, image = await loop.run_in_executor(executor, cap.read)
            if not ok:
                return
            yield Frame(
                source_id=self._source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=image,
            )
            sequence += 1
