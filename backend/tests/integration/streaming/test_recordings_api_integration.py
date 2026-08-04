"""T-063/T-064: exercises the real `/cameras/{id}/recording/*` + `/recordings`
routers end to end — a real `StartRecordingUseCase`/`StopRecordingUseCase`
driving a real `FfmpegRecordingWorker` subprocess, pointed at the local MP4
fixture path (the same trick `test_streams_api_integration.py` uses for live
view: no physical camera or RTSP server needed). Skip-guarded (ffmpeg/ffprobe
not installed in this environment — docs/TECHNICAL_DECISIONS.md TD-22,
mirroring TD-21's precedent for T-054), so this runs for real wherever both
binaries are present.

Reproduction steps for whoever has `ffmpeg`/`ffprobe` available, to manually
confirm T-064 against a real camera (this test only proves it against the
fixture): start a live stream (`POST /streams/{id}/start`), open
`GET /streams/{id}/mjpeg` in a browser tab to keep it consuming frames, then
`POST /cameras/{id}/recording/start`, wait, `POST .../recording/stop`, and
confirm both the MJPEG preview kept rendering throughout and the resulting
segment is valid per `ffprobe`.
"""

import asyncio
import functools
import shutil
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.get_camera import GetCameraUseCase
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.get_recording import GetRecordingUseCase
from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.application.use_cases.list_recordings import ListRecordingsUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.application.use_cases.start_recording import StartRecordingUseCase
from app.application.use_cases.stop_recording import StopRecordingUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.core.exception_handlers import register_exception_handlers
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.recording_repository import SqlRecordingRepository
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher
from app.infrastructure.streaming.recording_worker import FfmpegRecordingWorker
from app.infrastructure.streaming.rtsp_frame_source import RawRtspFrameSource
from app.infrastructure.streaming.stream_worker import StreamWorker
from app.interfaces.api.cameras import create_cameras_router
from app.interfaces.api.recordings import create_recordings_router
from app.interfaces.api.streams import create_streams_router
from tests.fixtures.onvif.fake_camera import FakeOnvifCamera

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed in this environment (docs/TECHNICAL_DECISIONS.md TD-22)",
)

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"


async def _build_app(db_path: Path, tmp_path: Path) -> FastAPI:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    camera_repository = SqlCameraRepository(
        build_session_factory(engine), CredentialCipher(Fernet.generate_key().decode())
    )
    recording_repository = SqlRecordingRepository(build_session_factory(engine))
    client_factory = functools.partial(FakeOnvifCamera, stream_uri=str(_FIXTURE_PATH))

    def build_gateway() -> OnvifCameraGateway:
        return OnvifCameraGateway(client_factory=client_factory)

    def build_stream_worker(camera: Camera, profile: StreamProfile) -> StreamWorker:
        frame_source_factory = functools.partial(
            RawRtspFrameSource, rtsp_url=str(_FIXTURE_PATH), source_id=str(camera.id)
        )
        return StreamWorker(
            frame_source_factory=frame_source_factory,
            backoff_schedule=[1, 2, 4],
            frame_queue_max_size=10,
        )

    def build_recording_worker(camera_id, rtsp_url: str) -> FfmpegRecordingWorker:  # type: ignore[no-untyped-def]
        return FfmpegRecordingWorker(
            camera_id=camera_id,
            rtsp_url=rtsp_url,
            output_dir=tmp_path / "recordings",
            segment_duration_seconds=300,
            ffmpeg_binary_path="ffmpeg",
            ffprobe_binary_path="ffprobe",
        )

    start_live_stream_use_case = StartLiveStreamUseCase(
        camera_gateway_factory=build_gateway,
        camera_repository=camera_repository,
        build_stream_worker=build_stream_worker,
    )
    registry = RecordingSessionRegistry()
    start_recording_use_case = StartRecordingUseCase(
        camera_gateway_factory=build_gateway,
        camera_repository=camera_repository,
        recording_repository=recording_repository,
        registry=registry,
        build_recording_worker=build_recording_worker,
    )
    stop_recording_use_case = StopRecordingUseCase(recording_repository, registry)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        create_cameras_router(
            build_onboard_camera_use_case=lambda: OnboardCameraUseCase(
                build_gateway(), camera_repository
            ),
            build_list_cameras_use_case=lambda: ListCamerasUseCase(camera_repository),
            build_get_camera_use_case=lambda: GetCameraUseCase(camera_repository),
            build_get_camera_config_use_case=lambda: GetCameraConfigUseCase(
                build_gateway(), camera_repository
            ),
            build_update_camera_config_use_case=lambda: UpdateCameraConfigUseCase(
                build_gateway(), camera_repository
            ),
        )
    )
    app.include_router(
        create_streams_router(
            lambda: start_live_stream_use_case, mjpeg_boundary="frame", mjpeg_jpeg_quality=80
        )
    )
    app.include_router(
        create_recordings_router(
            lambda: start_recording_use_case,
            lambda: stop_recording_use_case,
            lambda: ListRecordingsUseCase(recording_repository),
            lambda: GetRecordingUseCase(recording_repository),
        )
    )
    return app


async def _onboard(client: AsyncClient) -> str:
    response = await client.post(
        "/cameras",
        json={"ip_address": "10.0.0.5", "port": 8000, "username": "admin", "password": "x"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_start_wait_stop_list_shows_a_finalized_entry(tmp_path: Path) -> None:
    app = await _build_app(tmp_path / "cameras.db", tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        camera_id = await _onboard(client)

        start_response = await client.post(f"/cameras/{camera_id}/recording/start")
        assert start_response.status_code == 202
        in_progress = start_response.json()
        assert in_progress["ended_at"] is None

        list_while_running = await client.get("/recordings", params={"camera_id": camera_id})
        assert len(list_while_running.json()) == 1

        await asyncio.sleep(1.0)

        stop_response = await client.post(f"/cameras/{camera_id}/recording/stop")
        assert stop_response.status_code == 200
        segments = stop_response.json()
        assert len(segments) == 1
        assert segments[0]["id"] == in_progress["id"]
        assert segments[0]["ended_at"] is not None
        assert segments[0]["size_bytes"] > 0

        list_after_stop = await client.get("/recordings", params={"camera_id": camera_id})
        listed = list_after_stop.json()
        assert len(listed) == 1
        assert listed[0]["ended_at"] is not None


async def test_recording_and_live_view_run_concurrently_without_interference(
    tmp_path: Path,
) -> None:
    app = await _build_app(tmp_path / "cameras.db", tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        camera_id = await _onboard(client)

        async with client.stream("GET", f"/streams/{camera_id}/mjpeg") as mjpeg_response:
            assert mjpeg_response.status_code == 200

            start_response = await client.post(f"/cameras/{camera_id}/recording/start")
            assert start_response.status_code == 202

            body = b""
            async for chunk in mjpeg_response.aiter_bytes():
                body += chunk
                if body.count(b"\xff\xd8") >= 2:
                    break
            assert body.count(b"\xff\xd8") >= 2

            stop_response = await client.post(f"/cameras/{camera_id}/recording/stop")
            assert stop_response.status_code == 200
            segments = stop_response.json()
            assert len(segments) == 1
            assert segments[0]["size_bytes"] > 0

        await client.post(f"/streams/{camera_id}/stop")
