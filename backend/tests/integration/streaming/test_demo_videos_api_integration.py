"""M17/T-206: exercises the real `/demo/videos` router + WebSocket status
channel end to end — a real `StartDemoStreamUseCase`, a real `StreamWorker`
running a real `Mp4FileFrameSource` in a separate OS process, pointed at the
local MP4 fixture copied into a temp "demo videos" directory. Mirrors
`test_streams_api_integration.py`'s shape, simplified: no ONVIF/camera
onboarding step, since a demo video has no camera involved at all.
"""

import functools
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.list_demo_videos import ListDemoVideosUseCase
from app.application.use_cases.start_demo_stream import StartDemoStreamUseCase
from app.core.exception_handlers import register_exception_handlers
from app.infrastructure.streaming.local_demo_video_repository import LocalDemoVideoRepository
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource
from app.infrastructure.streaming.stream_worker import StreamWorker
from app.interfaces.api.demo_videos import create_demo_videos_router
from app.interfaces.websocket.demo_stream_status import create_demo_stream_status_router

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"


def _build_app(videos_dir: Path) -> FastAPI:
    repository = LocalDemoVideoRepository(videos_dir)

    def build_stream_worker(video_id: str, file_path: Path) -> StreamWorker:
        frame_source_factory = functools.partial(
            Mp4FileFrameSource, file_path=str(file_path), source_id=video_id, loop=True
        )
        return StreamWorker(
            frame_source_factory=frame_source_factory,
            backoff_schedule=[1, 2, 4],
            frame_queue_max_size=10,
        )

    start_demo_stream_use_case = StartDemoStreamUseCase(
        demo_video_repository=repository,
        build_stream_worker=build_stream_worker,
    )

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        create_demo_videos_router(
            lambda: ListDemoVideosUseCase(repository),
            lambda: start_demo_stream_use_case,
            mjpeg_boundary="frame",
            mjpeg_jpeg_quality=80,
        )
    )
    app.include_router(
        create_demo_stream_status_router(
            lambda: start_demo_stream_use_case, poll_interval_seconds=0.05
        )
    )
    return app


def _seed_video(videos_dir: Path) -> str:
    videos_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(_FIXTURE_PATH, videos_dir / "sample.mp4")
    return "sample"


async def test_list_videos_returns_the_seeded_fixture(tmp_path: Path) -> None:
    video_id = _seed_video(tmp_path)
    app = _build_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/demo/videos")

    assert response.status_code == 200
    assert response.json() == [{"id": video_id, "filename": "sample.mp4"}]


async def test_mjpeg_endpoint_streams_real_frames_from_a_real_worker_process(
    tmp_path: Path,
) -> None:
    video_id = _seed_video(tmp_path)
    app = _build_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", f"/demo/videos/{video_id}/mjpeg") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"

            body = b""
            async for chunk in response.aiter_bytes():
                body += chunk
                if body.count(b"\xff\xd8") >= 2:
                    break

            assert b"--frame\r\n" in body
            assert b"Content-Type: image/jpeg" in body

        stop_response = await client.post(f"/demo/videos/{video_id}/stop")
        assert stop_response.status_code == 202
        assert stop_response.json()["state"] == "stopped"


async def test_start_status_stop_lifecycle_via_api(tmp_path: Path) -> None:
    video_id = _seed_video(tmp_path)
    app = _build_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_response = await client.post(f"/demo/videos/{video_id}/start")
        assert start_response.status_code == 202

        status_response = await client.get(f"/demo/videos/{video_id}/status")
        assert status_response.status_code == 200
        assert status_response.json()["state"] in ("connecting", "connected")

        stop_response = await client.post(f"/demo/videos/{video_id}/stop")
        assert stop_response.status_code == 202
        assert stop_response.json()["state"] == "stopped"


async def test_start_unknown_video_id_returns_404(tmp_path: Path) -> None:
    app = _build_app(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/demo/videos/unknown/start")

    assert response.status_code == 404


def test_demo_stream_status_websocket_pushes_status(tmp_path: Path) -> None:
    video_id = _seed_video(tmp_path)
    app = _build_app(tmp_path)
    with (
        TestClient(app) as client,
        client.websocket_connect(f"/ws/demo/videos/{video_id}/status") as websocket,
    ):
        message = websocket.receive_json()
        assert message["state"] == "stopped"
