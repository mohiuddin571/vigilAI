import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

import structlog

from app.application.ports.recording_worker import IRecordingWorker
from app.domain.entities.recording import Recording
from app.domain.exceptions import FrameSourceUnavailableError

logger = structlog.get_logger(__name__)

_TERMINATE_TIMEOUT_SECONDS = 10.0
_KILL_TIMEOUT_SECONDS = 5.0
_CODEC_PROBE_TIMEOUT_SECONDS = 10.0

# QuickTime/AVFoundation refuses to play an HEVC stream muxed into MP4 with
# the `hev1` codec tag (in-band parameter sets — how RTSP cameras normally
# send HEVC), even though the video itself decodes fine (ffmpeg/VLC play it
# without issue). It only accepts `hvc1` (out-of-band parameter sets in the
# sample description). Confirmed against a real Matrix MIDR20FL28CWS camera's
# RTSP override URL (docs/TECHNICAL_DECISIONS.md TD-22): a `-c copy` segment
# muxed without this tag override produced a file QuickTime rejected as
# "not compatible," identical symptoms to this well-documented ffmpeg/Apple
# interop gap. Retagging container metadata is lossless for a stream-copy
# (TD-04) — no re-encode, no code-vs-tag mismatch, since we only apply it
# when ffprobe confirms the input is actually HEVC.
_HEVC_MP4_TAG_FIX = ["-tag:v", "hvc1"]


class FfmpegRecordingWorker(IRecordingWorker):
    """`IRecordingWorker` implementation: an `ffmpeg` stream-copy segment-muxer subprocess.

    TD-04: ffmpeg via subprocess, `-c copy` (no re-encode), reading directly
    from the RTSP source URL it's constructed with — independent of the
    analytics decode path. Unlike `StreamWorker` (TD-05), this does not use
    Python `multiprocessing`: ffmpeg itself is already the isolated OS
    process doing the I/O-heavy work, so there's no Python decode loop left
    to isolate.

    Segment naming is deterministic (`{session_id}_%03d.mp4`, `session_id`
    generated fresh in `start()`), not ffmpeg's `-strftime` — the exact
    output path of the first segment must be knowable before ffmpeg is even
    spawned, per docs/TECHNICAL_DECISIONS.md TD-22. Segment metadata
    (duration/size) is extracted via `ffprobe` once ffmpeg has exited
    (`stop()`), not tracked live during the recording — this milestone has no
    requirement to expose in-progress segment metadata before a session ends.

    Never logs `rtsp_url` or raw ffmpeg/ffprobe output: the URL can embed
    camera credentials, and TD-15/AGENTS.md forbid that appearing in logs.
    """

    def __init__(
        self,
        camera_id: UUID,
        rtsp_url: str,
        output_dir: Path,
        segment_duration_seconds: int,
        ffmpeg_binary_path: str,
        ffprobe_binary_path: str,
    ) -> None:
        self._camera_id = camera_id
        self._rtsp_url = rtsp_url
        self._output_dir = output_dir / str(camera_id)
        self._segment_duration_seconds = segment_duration_seconds
        self._ffmpeg_binary_path = ffmpeg_binary_path
        self._ffprobe_binary_path = ffprobe_binary_path
        self._process: asyncio.subprocess.Process | None = None
        self._session_id: UUID | None = None
        self._session_started_at: datetime | None = None
        self._first_recording_id: UUID | None = None

    async def start(self) -> Recording:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        session_id = uuid4()
        session_started_at = datetime.now(UTC)
        first_recording_id = uuid4()
        self._session_id = session_id
        self._session_started_at = session_started_at
        self._first_recording_id = first_recording_id

        video_codec = await self._probe_video_codec()

        pattern = self._output_dir / f"{session_id}_%03d.mp4"
        argv = [self._ffmpeg_binary_path, "-y"]
        if urlparse(self._rtsp_url).scheme in {"rtsp", "rtsps"}:
            argv += ["-rtsp_transport", "tcp"]
        argv += ["-i", self._rtsp_url, "-c", "copy"]
        if video_codec == "hevc":
            argv += _HEVC_MP4_TAG_FIX
        argv += [
            "-map",
            "0",
            "-f",
            "segment",
            "-segment_time",
            str(self._segment_duration_seconds),
            "-reset_timestamps",
            "1",
            str(pattern),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise FrameSourceUnavailableError(
                f"Could not start ffmpeg recording for camera {self._camera_id}"
            ) from exc
        self._process = process
        logger.info(
            "recording_worker.started",
            camera_id=str(self._camera_id),
            pid=process.pid,
            segment_duration_seconds=self._segment_duration_seconds,
        )

        first_segment_path = self._output_dir / f"{session_id}_000.mp4"
        return Recording(
            id=first_recording_id,
            camera_id=self._camera_id,
            file_path=str(first_segment_path),
            started_at=session_started_at,
        )

    async def stop(self) -> list[Recording]:
        process = self._process
        session_id = self._session_id
        session_started_at = self._session_started_at
        first_recording_id = self._first_recording_id
        if process is None or session_id is None or session_started_at is None:
            return []
        assert first_recording_id is not None

        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_TIMEOUT_SECONDS)
            except TimeoutError:
                logger.warning(
                    "recording_worker.force_kill",
                    camera_id=str(self._camera_id),
                    pid=process.pid,
                )
                process.kill()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=_KILL_TIMEOUT_SECONDS)

        logger.info(
            "recording_worker.stopped",
            camera_id=str(self._camera_id),
            pid=process.pid,
            returncode=process.returncode,
        )
        self._process = None

        segment_paths = sorted(self._output_dir.glob(f"{session_id}_*.mp4"))
        valid_segments: list[tuple[Path, float, int]] = []
        for path in segment_paths:
            duration_seconds = await self._probe_duration(path)
            if duration_seconds is None:
                # An unfinalized/corrupt segment (e.g. a forced kill
                # mid-write left no valid moov atom) — dropped rather than
                # persisted as a broken row.
                continue
            valid_segments.append((path, duration_seconds, path.stat().st_size))

        segments: list[Recording] = []
        segment_started_at = session_started_at
        for index, (path, duration_seconds, size_bytes) in enumerate(valid_segments):
            segment_ended_at = segment_started_at + timedelta(seconds=duration_seconds)
            segment_id = first_recording_id if index == 0 else uuid4()
            segments.append(
                Recording(
                    id=segment_id,
                    camera_id=self._camera_id,
                    file_path=str(path),
                    started_at=segment_started_at,
                    ended_at=segment_ended_at,
                    size_bytes=size_bytes,
                )
            )
            segment_started_at = segment_ended_at

        return segments

    async def _probe_video_codec(self) -> str | None:
        """Best-effort: identify the input's video codec (e.g. `"hevc"`) before muxing.

        Needed to decide the `-tag:v hvc1` fix above. Never logs
        `self._rtsp_url` (TD-15) even on failure. Failure (including a
        timeout) is not fatal — falls back to no tag override, matching this
        worker's prior behavior for every non-HEVC source.
        """
        argv = [self._ffprobe_binary_path, "-v", "error"]
        if urlparse(self._rtsp_url).scheme in {"rtsp", "rtsps"}:
            argv += ["-rtsp_transport", "tcp"]
        argv += [
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            self._rtsp_url,
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
            )
        except OSError:
            return None
        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(), timeout=_CODEC_PROBE_TIMEOUT_SECONDS
            )
        except TimeoutError:
            # Avoid leaking an orphaned ffprobe subprocess (the exact class
            # of bug docs/TECHNICAL_DECISIONS.md TD-20 already documents for
            # StreamWorker children).
            process.kill()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=_KILL_TIMEOUT_SECONDS)
            return None
        if process.returncode != 0:
            return None
        codec_name = stdout.decode().strip()
        return codec_name or None

    async def _probe_duration(self, path: Path) -> float | None:
        try:
            process = await asyncio.create_subprocess_exec(
                self._ffprobe_binary_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await process.communicate()
        except OSError:
            return None
        if process.returncode != 0:
            return None
        try:
            return float(stdout.decode().strip())
        except ValueError:
            return None
