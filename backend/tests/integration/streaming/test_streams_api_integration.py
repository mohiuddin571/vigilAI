"""T-052/T-053: exercises the real `/streams` router + WebSocket status channel end
to end — real FastAPI routes, a real `StartLiveStreamUseCase`, a real `StreamWorker`
running a real `RawRtspFrameSource` in a separate OS process (T-023), pointed at
the local MP4 fixture path (the same real `cv2.VideoCapture` decode a real
`rtsp://` URL would take — no physical camera or RTSP server needed, per
docs/TECHNICAL_DECISIONS.md TD-21). The upfront ONVIF reachability check inside
`StartLiveStreamUseCase.execute()` still runs for real against a fixture-driven
fake ONVIF client (T-037's pattern) — that call happens in this process, not the
spawned child, so it doesn't need `OnvifRtspFrameSource`/the ONVIF gateway to
survive a `multiprocessing` "spawn" pickle round-trip (which would require the
`tests` package itself, not just `app`, to be importable inside the freshly
spawned interpreter — true for `RawRtspFrameSource`, since `app` is a properly
installed package, but not for anything under `tests/`).
"""

import asyncio
import functools
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.get_camera import GetCameraUseCase
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.core.exception_handlers import register_exception_handlers
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher
from app.infrastructure.streaming.rtsp_frame_source import RawRtspFrameSource
from app.infrastructure.streaming.stream_worker import StreamWorker
from app.interfaces.api.cameras import create_cameras_router
from app.interfaces.api.streams import create_streams_router
from app.interfaces.websocket.stream_status import create_stream_status_router
from tests.fixtures.onvif.fake_camera import FakeOnvifCamera

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"


async def _build_app(db_path: Path) -> FastAPI:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    repository = SqlCameraRepository(
        build_session_factory(engine), CredentialCipher(Fernet.generate_key().decode())
    )
    # GetStreamUri resolves to the local MP4 fixture: the same real
    # `cv2.VideoCapture` decode path a real `rtsp://` URL would take, without
    # a physical camera or RTSP server (see module docstring / TD-21).
    client_factory = functools.partial(FakeOnvifCamera, stream_uri=str(_FIXTURE_PATH))

    def build_gateway() -> OnvifCameraGateway:
        return OnvifCameraGateway(client_factory=client_factory)

    def build_stream_worker(camera: Camera, profile: StreamProfile) -> StreamWorker:
        # `RawRtspFrameSource`, not `OnvifRtspFrameSource`, deliberately — see
        # the module docstring for why the picklable-across-`spawn` factory
        # must stay inside the `app` package here.
        frame_source_factory = functools.partial(
            RawRtspFrameSource, rtsp_url=str(_FIXTURE_PATH), source_id=str(camera.id)
        )
        return StreamWorker(
            frame_source_factory=frame_source_factory,
            backoff_schedule=[1, 2, 4],
            frame_queue_max_size=10,
        )

    start_live_stream_use_case = StartLiveStreamUseCase(
        camera_gateway_factory=build_gateway,
        camera_repository=repository,
        build_stream_worker=build_stream_worker,
    )

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        create_cameras_router(
            build_onboard_camera_use_case=lambda: OnboardCameraUseCase(build_gateway(), repository),
            build_list_cameras_use_case=lambda: ListCamerasUseCase(repository),
            build_get_camera_use_case=lambda: GetCameraUseCase(repository),
            build_get_camera_config_use_case=lambda: GetCameraConfigUseCase(
                build_gateway(), repository
            ),
            build_update_camera_config_use_case=lambda: UpdateCameraConfigUseCase(
                build_gateway(), repository
            ),
        )
    )
    app.include_router(
        create_streams_router(
            lambda: start_live_stream_use_case, mjpeg_boundary="frame", mjpeg_jpeg_quality=80
        )
    )
    app.include_router(
        create_stream_status_router(lambda: start_live_stream_use_case, poll_interval_seconds=0.05)
    )
    return app


async def _onboard(client: AsyncClient) -> str:
    response = await client.post(
        "/cameras",
        json={"ip_address": "10.0.0.5", "port": 8000, "username": "admin", "password": "x"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_mjpeg_endpoint_streams_real_frames_from_a_real_worker_process(
    tmp_path: Path,
) -> None:
    app = await _build_app(tmp_path / "cameras.db")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        camera_id = await _onboard(client)

        async with client.stream("GET", f"/streams/{camera_id}/mjpeg") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"

            body = b""
            async for chunk in response.aiter_bytes():
                body += chunk
                # Two JPEG SOI markers proves at least two distinct frames
                # were streamed, not a single static image.
                if body.count(b"\xff\xd8") >= 2:
                    break

            assert b"--frame\r\n" in body
            assert b"Content-Type: image/jpeg" in body

        stop_response = await client.post(f"/streams/{camera_id}/stop")
        assert stop_response.status_code == 202
        assert stop_response.json()["state"] == "stopped"


async def test_start_status_stop_lifecycle_via_api(tmp_path: Path) -> None:
    app = await _build_app(tmp_path / "cameras.db")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        camera_id = await _onboard(client)

        start_response = await client.post(f"/streams/{camera_id}/start")
        assert start_response.status_code == 202

        status_response = await client.get(f"/streams/{camera_id}/status")
        assert status_response.status_code == 200
        assert status_response.json()["state"] in ("connecting", "connected")

        stop_response = await client.post(f"/streams/{camera_id}/stop")
        assert stop_response.status_code == 202
        assert stop_response.json()["state"] == "stopped"


def test_stream_status_websocket_pushes_status(tmp_path: Path) -> None:
    app = asyncio.run(_build_app(tmp_path / "cameras.db"))
    with TestClient(app) as client:
        onboard_response = client.post(
            "/cameras",
            json={"ip_address": "10.0.0.5", "port": 8000, "username": "admin", "password": "x"},
        )
        camera_id = onboard_response.json()["id"]

        with client.websocket_connect(f"/ws/streams/{camera_id}/status") as websocket:
            message = websocket.receive_json()
            assert message["state"] == "stopped"
