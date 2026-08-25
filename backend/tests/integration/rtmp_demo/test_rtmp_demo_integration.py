"""End-to-end integration test for the RTMP Push/Consume Demo (docs/RTMP_DEMO.md).

Exercises the real pipeline this demo exists to prove:

    MP4 fixture -> FfmpegRtmpPublisher -> MediaMtxServerController -> RtmpFrameSource (via
    StreamWorker) -> decoded frames

No fakes for the RTMP hop itself, since the whole point of this demo is that
the video actually travels through a real RTMP publish/ingest/consume round
trip, not that the pipeline's *shape* is correct in isolation (unit tests
already cover that with fakes — see `tests/unit/application/test_*rtmp*.py`).

Requires `mediamtx` and `ffmpeg` on PATH; skipped automatically if either is
missing (both are demo-only dependencies, not required to run the rest of
the test suite — see `docs/RTMP_DEMO.md`'s installation note).
"""

import asyncio
import functools
import shutil
import socket
from pathlib import Path

import pytest

from app.infrastructure.rtmp_demo.ffmpeg_publisher import FfmpegRtmpPublisher, build_rtmp_url
from app.infrastructure.rtmp_demo.mediamtx_server import MediaMtxServerController
from app.infrastructure.rtmp_demo.rtmp_frame_source import RtmpFrameSource
from app.infrastructure.streaming.stream_worker import StreamWorker

pytestmark = pytest.mark.skipif(
    shutil.which("mediamtx") is None or shutil.which("ffmpeg") is None,
    reason="requires mediamtx and ffmpeg on PATH — brew install mediamtx (see docs/RTMP_DEMO.md)",
)

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"
_HOST = "127.0.0.1"
_APP_NAME = "live"
_STREAM_KEY = "integration-test"
# Real, observed latency: MediaMTX only reports a path "available" a few
# seconds after ffmpeg opens its RTMP connection (TCP connect -> RTMP
# handshake -> ffmpeg's own encoder startup -> first keyframe reaching the
# server). The consumer is deliberately started before that happens (proving
# the same reconnect/backoff path used everywhere else in this codebase, not
# a fixed "wait for the stream to exist" step) — so this budget must cover
# several failed-then-retried open attempts, not just one.
_CONSUMER_OPEN_TIMEOUT_MS = 3000
_CONSUMER_READ_TIMEOUT_MS = 3000
_STARTUP_TIMEOUT_SECONDS = 45.0


def _free_tcp_port() -> int:
    """A currently-unused local TCP port, so this test never collides with a developer's own
    manually-running RTMP demo server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((_HOST, 0))
        return sock.getsockname()[1]


async def test_publish_then_consume_round_trip_and_recovers_after_publisher_restart(
    tmp_path: Path,
) -> None:
    port = _free_tcp_port()

    server = MediaMtxServerController(
        "mediamtx",
        tmp_path,
        host=_HOST,
        port=port,
        app_name=_APP_NAME,
        stream_key=_STREAM_KEY,
        publish_username=None,
        publish_password=None,
        read_username=None,
        read_password=None,
    )
    publisher = FfmpegRtmpPublisher(
        "ffmpeg",
        host=_HOST,
        port=port,
        app_name=_APP_NAME,
        stream_key=_STREAM_KEY,
        publish_username=None,
        publish_password=None,
        video_bitrate_kbps=500,
        resolution="320x240",
        fps=10,
    )
    rtmp_url = build_rtmp_url(_HOST, port, _APP_NAME, _STREAM_KEY, None, None)
    consumer_factory = functools.partial(
        RtmpFrameSource,
        rtmp_url=rtmp_url,
        source_id="rtmp-demo-integration-test",
        open_timeout_ms=_CONSUMER_OPEN_TIMEOUT_MS,
        read_timeout_ms=_CONSUMER_READ_TIMEOUT_MS,
    )
    consumer = StreamWorker(
        frame_source_factory=consumer_factory,
        backoff_schedule=[0.5, 1.0, 1.5],
        frame_queue_max_size=10,
    )

    try:
        await server.start()
        assert server.status().running is True

        await publisher.start("integration-test", _FIXTURE_PATH)
        assert publisher.status().running is True

        await consumer.start()
        frame = await asyncio.wait_for(anext(consumer.frames()), timeout=_STARTUP_TIMEOUT_SECONDS)
        assert frame.image.shape[0] > 0
        assert frame.image.shape[1] > 0

        # Publisher stops unexpectedly (request scenario #7) -> the consumer's
        # own ReconnectSupervisor (unmodified, shared with every other
        # IFrameSource in this codebase) must notice and start retrying.
        await publisher.stop()
        assert publisher.status().running is False

        # Publisher restarts (request scenario #11/#12 from the test flow) ->
        # the same consumer recovers without being told to reconnect.
        await publisher.start("integration-test", _FIXTURE_PATH)
        recovered = await asyncio.wait_for(
            anext(consumer.frames()), timeout=_STARTUP_TIMEOUT_SECONDS
        )
        assert recovered.image.shape[0] > 0
    finally:
        await consumer.stop()
        await publisher.stop()
        await server.stop()
