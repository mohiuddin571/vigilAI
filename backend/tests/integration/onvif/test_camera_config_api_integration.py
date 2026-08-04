"""T-042: the two required M4 tests, run through the real FastAPI router
(`GET`/`PATCH /cameras/{id}/config`), the real `OnvifCameraGateway`, the
fixture-driven fake ONVIF client, and a real `SqlCameraRepository`.

- "PATCH of a supported field is reflected on the next GET" (AC #2).
- "PATCH of an unsupported field/value fails cleanly with a typed 4xx"
  (AC #3) — never a raw SOAP fault or stack trace.
"""

import functools
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.get_camera import GetCameraUseCase
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.core.exception_handlers import register_exception_handlers
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher
from app.interfaces.api.cameras import create_cameras_router
from tests.fixtures.onvif.fake_camera import (
    FakeOnvifCamera,
    load_profiles,
    load_video_encoder_configuration_options,
    load_video_encoder_configurations,
)


async def _build_app(db_path: Path) -> FastAPI:
    """Wires the real router to real use cases the same way `container.py`
    does, but with a single shared fake-camera client factory (rather than
    the real `ONVIFCamera`) so every request "reconnects" to the same
    in-memory camera state — see test_camera_config_integration.py's
    `_shared_camera_client_factory` for why that matters.
    """
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    repository = SqlCameraRepository(
        build_session_factory(engine), CredentialCipher(Fernet.generate_key().decode())
    )
    client_factory = functools.partial(
        FakeOnvifCamera,
        profiles=load_profiles(),
        video_encoder_configs=load_video_encoder_configurations(),
        video_encoder_options=load_video_encoder_configuration_options(),
    )

    def build_gateway() -> OnvifCameraGateway:
        return OnvifCameraGateway(client_factory=client_factory)

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
    return app


async def test_patch_supported_field_reflected_on_next_get(tmp_path: Path) -> None:
    app = await _build_app(tmp_path / "cameras.db")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        onboard_response = await client.post(
            "/cameras",
            json={"ip_address": "10.0.0.5", "port": 8000, "username": "admin", "password": "x"},
        )
        assert onboard_response.status_code == 201
        camera_id = onboard_response.json()["id"]

        get_response = await client.get(
            f"/cameras/{camera_id}/config", params={"profile_id": "Profile_1"}
        )
        assert get_response.status_code == 200
        body = get_response.json()
        assert body["bitrate_kbps"] == 4096
        assert body["capabilities"]["bitrate_min_kbps"] == 512
        assert body["capabilities"]["bitrate_max_kbps"] == 8192

        patch_response = await client.patch(
            f"/cameras/{camera_id}/config",
            params={"profile_id": "Profile_1"},
            json={"bitrate_kbps": 2048},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["bitrate_kbps"] == 2048

        get_after_patch = await client.get(
            f"/cameras/{camera_id}/config", params={"profile_id": "Profile_1"}
        )
        assert get_after_patch.status_code == 200
        assert get_after_patch.json()["bitrate_kbps"] == 2048
        # Unrelated fields are untouched.
        assert get_after_patch.json()["resolution"] == "1920x1080"


async def test_patch_unsupported_field_returns_typed_4xx_not_silently_ignored(
    tmp_path: Path,
) -> None:
    app = await _build_app(tmp_path / "cameras.db")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        onboard_response = await client.post(
            "/cameras",
            json={"ip_address": "10.0.0.5", "port": 8000, "username": "admin", "password": "x"},
        )
        camera_id = onboard_response.json()["id"]

        patch_response = await client.patch(
            f"/cameras/{camera_id}/config",
            params={"profile_id": "Profile_1"},
            json={"codec": "MJPEG"},
        )

        assert patch_response.status_code == 422
        assert "detail" in patch_response.json()

        # Never silently ignored: a subsequent GET shows the field unchanged.
        get_response = await client.get(
            f"/cameras/{camera_id}/config", params={"profile_id": "Profile_1"}
        )
        assert get_response.json()["codec"] == "H264"
