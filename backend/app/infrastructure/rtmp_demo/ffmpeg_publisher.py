import asyncio
import contextlib
from pathlib import Path
from urllib.parse import quote

import structlog

from app.application.ports.rtmp_publisher import IRtmpPublisher
from app.domain.exceptions import RtmpPublisherError
from app.domain.value_objects.rtmp_publisher_status import RtmpPublisherStatus

logger = structlog.get_logger(__name__)

_TERMINATE_TIMEOUT_SECONDS = 5.0
_KILL_TIMEOUT_SECONDS = 3.0


def build_rtmp_url(
    host: str,
    port: int,
    app_name: str,
    stream_key: str,
    username: str | None,
    password: str | None,
) -> str:
    """Build `rtmp://[user:pass@]host:port/app/stream_key`, shared by the publisher and the
    consumer (`rtmp_frame_source.py`) so both sides always agree on the destination."""
    credentials = ""
    if username and password:
        credentials = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return f"rtmp://{credentials}{host}:{port}/{app_name}/{stream_key}"


class FfmpegRtmpPublisher(IRtmpPublisher):
    """`IRtmpPublisher` implementation: an `ffmpeg` subprocess looping a local video file as a
    simulated RTMP camera (docs/RTMP_DEMO.md).

    Reuses `FfmpegRecordingWorker`'s subprocess-ownership shape (TD-22):
    plain `asyncio.create_subprocess_exec`, terminate-then-kill on `stop()`.
    Unlike that worker (`-c copy`, no re-encode, reading an already-encoded
    RTSP source), this one re-encodes with libx264 at a configured
    resolution/bitrate/fps — there's no "already encoded the way we want"
    input here, just a raw source video file, and the point of this demo is
    to prove a real encode -> push -> ingest -> pull -> decode round trip,
    not to stream-copy.

    Never logs the RTMP destination URL: it may embed publish credentials
    (TD-15/AGENTS.md).
    """

    def __init__(
        self,
        ffmpeg_binary_path: str,
        *,
        host: str,
        port: int,
        app_name: str,
        stream_key: str,
        publish_username: str | None,
        publish_password: str | None,
        video_bitrate_kbps: int,
        resolution: str,
        fps: int,
    ) -> None:
        self._ffmpeg_binary_path = ffmpeg_binary_path
        self._host = host
        self._port = port
        self._app_name = app_name
        self._stream_key = stream_key
        self._publish_username = publish_username
        self._publish_password = publish_password
        self._video_bitrate_kbps = video_bitrate_kbps
        self._resolution = resolution
        self._fps = fps
        self._process: asyncio.subprocess.Process | None = None
        self._video_id: str | None = None

    async def start(self, video_id: str, video_path: Path) -> None:
        if self._process is not None and self._process.returncode is None:
            return
        if not video_path.is_file():
            raise RtmpPublisherError(f"Video file does not exist: {video_path.name}")

        url = build_rtmp_url(
            self._host,
            self._port,
            self._app_name,
            self._stream_key,
            self._publish_username,
            self._publish_password,
        )
        argv = [
            self._ffmpeg_binary_path,
            "-re",
            "-stream_loop",
            "-1",
            "-i",
            str(video_path),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-s",
            self._resolution,
            "-r",
            str(self._fps),
            "-b:v",
            f"{self._video_bitrate_kbps}k",
            "-f",
            "flv",
            url,
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise RtmpPublisherError("Could not start the RTMP publisher (ffmpeg).") from exc

        self._process = process
        self._video_id = video_id
        logger.info("rtmp_demo.publisher_started", pid=process.pid, video_id=video_id)

    async def stop(self) -> None:
        process = self._process
        if process is None:
            return
        self._process = None
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_TIMEOUT_SECONDS)
            except TimeoutError:
                logger.warning("rtmp_demo.publisher_force_kill", pid=process.pid)
                process.kill()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=_KILL_TIMEOUT_SECONDS)
        logger.info("rtmp_demo.publisher_stopped", pid=process.pid, returncode=process.returncode)
        self._video_id = None

    def status(self) -> RtmpPublisherStatus:
        process = self._process
        if process is None:
            return RtmpPublisherStatus(running=False)
        if process.returncode is None:
            return RtmpPublisherStatus(running=True, pid=process.pid, video_id=self._video_id)
        # `stop()` always clears `self._process` before this branch could be
        # reached from a deliberate stop — landing here means ffmpeg exited
        # on its own (bad/corrupt input, server unreachable, auth
        # rejected, ...), i.e. request scenarios #2/#4/#7/#10.
        return RtmpPublisherStatus(
            running=False,
            video_id=self._video_id,
            exited_unexpectedly=True,
            error=f"ffmpeg exited unexpectedly (code {process.returncode})",
        )
