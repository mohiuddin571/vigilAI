"""Real-hardware camera-configuration check — skipped by default (pyproject `-m "not hardware"`).

Verifies T-043's hardware DoD: editing a real supported field updates the
physical camera, and the change is reflected on a subsequent GET.

Run explicitly with the physical camera's details once available:

    TEST_CAMERA_IP=... TEST_CAMERA_USERNAME=... TEST_CAMERA_PASSWORD=... \\
        TEST_CAMERA_PROFILE_TOKEN=... \\
        uv run pytest -m hardware tests/integration/onvif/test_camera_config_hardware.py
"""

import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.application.dto.camera_config import CameraConfigUpdate
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.domain.value_objects.bitrate import BitrateKbps
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher

pytestmark = pytest.mark.hardware


@pytest.mark.skipif(
    not os.environ.get("TEST_CAMERA_IP") or not os.environ.get("TEST_CAMERA_PROFILE_TOKEN"),
    reason=(
        "Set TEST_CAMERA_IP/TEST_CAMERA_USERNAME/TEST_CAMERA_PASSWORD/"
        "TEST_CAMERA_PROFILE_TOKEN to run against hardware."
    ),
)
async def test_update_real_camera_supported_field_reflected_on_camera(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'cameras.db'}")
    await init_db(engine)
    repository = SqlCameraRepository(
        build_session_factory(engine), CredentialCipher(Fernet.generate_key().decode())
    )

    camera = await OnboardCameraUseCase(OnvifCameraGateway(), repository).execute(
        ip_address=os.environ["TEST_CAMERA_IP"],
        username=os.environ["TEST_CAMERA_USERNAME"],
        password=os.environ["TEST_CAMERA_PASSWORD"],
        port=int(os.environ.get("TEST_CAMERA_PORT", "80")),
    )
    profile_id = os.environ["TEST_CAMERA_PROFILE_TOKEN"]

    before = await GetCameraConfigUseCase(OnvifCameraGateway(), repository).execute(
        camera.id, profile_id
    )
    # Nudge the bitrate within the camera's own reported range, staying clear
    # of its current value so a no-op couldn't accidentally pass the assertion.
    if before.capabilities.bitrate_min_kbps is None:
        pytest.skip("Camera did not report a bitrate range for this profile")
    candidate = before.capabilities.bitrate_min_kbps
    if candidate == before.profile.bitrate.value:
        candidate = before.capabilities.bitrate_max_kbps

    updated = await UpdateCameraConfigUseCase(OnvifCameraGateway(), repository).execute(
        camera.id, profile_id, CameraConfigUpdate(bitrate=BitrateKbps(value=candidate))
    )
    assert updated.bitrate.value == candidate

    after = await GetCameraConfigUseCase(OnvifCameraGateway(), repository).execute(
        camera.id, profile_id
    )
    assert after.profile.bitrate.value == candidate
