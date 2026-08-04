"""Real-hardware onboarding check — skipped by default (pyproject `-m "not hardware"`).

Run explicitly with the physical camera's details once available:

    TEST_CAMERA_IP=... TEST_CAMERA_USERNAME=... TEST_CAMERA_PASSWORD=... \\
        uv run pytest -m hardware tests/integration/onvif/test_onboard_camera_hardware.py
"""

import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher

pytestmark = pytest.mark.hardware


@pytest.mark.skipif(
    not os.environ.get("TEST_CAMERA_IP"),
    reason="Set TEST_CAMERA_IP/TEST_CAMERA_USERNAME/TEST_CAMERA_PASSWORD to run against hardware.",
)
async def test_onboard_real_camera(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'cameras.db'}")
    await init_db(engine)
    repository = SqlCameraRepository(
        build_session_factory(engine), CredentialCipher(Fernet.generate_key().decode())
    )
    use_case = OnboardCameraUseCase(OnvifCameraGateway(), repository)

    camera = await use_case.execute(
        ip_address=os.environ["TEST_CAMERA_IP"],
        username=os.environ["TEST_CAMERA_USERNAME"],
        password=os.environ["TEST_CAMERA_PASSWORD"],
        port=int(os.environ.get("TEST_CAMERA_PORT", "80")),
    )

    assert camera.manufacturer is not None
    assert len(camera.stream_profiles) >= 1
