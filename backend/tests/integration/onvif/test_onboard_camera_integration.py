"""T-033: onboards a fixture-driven camera end-to-end against the *real* repository.

Exercises `OnvifCameraGateway` (with a fake ONVIF client injected — see
tests/fixtures/onvif/fake_camera.py) and the real `SqlCameraRepository`
against a temp SQLite file, proving AC #3 ("onboarding is persisted and
survives an API restart") by re-opening a second repository instance against
the same file rather than reusing the first.
"""

import functools
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.domain.exceptions import CameraAuthenticationError, CameraUnreachableError
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher
from tests.fixtures.onvif.fake_camera import FakeOnvifCamera


async def _open_repository(db_path: Path, encryption_key: str) -> SqlCameraRepository:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    return SqlCameraRepository(build_session_factory(engine), CredentialCipher(encryption_key))


async def test_onboard_camera_persists_across_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "cameras.db"
    # The same key a real deployment would keep in `.env` across restarts.
    encryption_key = Fernet.generate_key().decode()

    repository = await _open_repository(db_path, encryption_key)
    gateway = OnvifCameraGateway(client_factory=FakeOnvifCamera)
    onboarded = await OnboardCameraUseCase(gateway, repository).execute(
        ip_address="10.0.0.5", username="admin", password="s3cret-pass", port=8000
    )

    assert onboarded.manufacturer == "Acme Vision"
    assert onboarded.model == "AV-2000"
    # profiles.json has 3 entries; "Profile_3" has no VideoEncoderConfiguration
    # and is legitimately skipped (see mappers.map_profile).
    assert len(onboarded.stream_profiles) == 2
    assert {p.name for p in onboarded.stream_profiles} == {"MainStream", "SubStream"}

    # Simulate an API restart: a brand-new repository instance, same DB file.
    restarted_repository = await _open_repository(db_path, encryption_key)
    cameras_after_restart = await ListCamerasUseCase(restarted_repository).execute()

    assert len(cameras_after_restart) == 1
    persisted = cameras_after_restart[0]
    assert persisted.id == onboarded.id
    assert persisted.ip_address == "10.0.0.5"
    assert persisted.port == 8000
    assert persisted.password == "s3cret-pass"  # decrypted correctly with the same key
    assert len(persisted.stream_profiles) == 2


async def test_onboard_camera_wrong_credentials_raises_typed_error_and_persists_nothing(
    tmp_path: Path,
) -> None:
    repository = await _open_repository(tmp_path / "cameras.db", Fernet.generate_key().decode())
    gateway = OnvifCameraGateway(
        client_factory=functools.partial(
            FakeOnvifCamera, fail_with=Exception("Sender: wsse:FailedAuthentication")
        )
    )
    use_case = OnboardCameraUseCase(gateway, repository)

    with pytest.raises(CameraAuthenticationError):
        await use_case.execute(ip_address="10.0.0.5", username="admin", password="wrong")

    assert await repository.list() == []


async def test_onboard_camera_unreachable_host_raises_typed_error(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "cameras.db", Fernet.generate_key().decode())
    gateway = OnvifCameraGateway(
        client_factory=functools.partial(
            FakeOnvifCamera, fail_with=TimeoutError("connection timed out")
        )
    )
    use_case = OnboardCameraUseCase(gateway, repository)

    with pytest.raises(CameraUnreachableError):
        await use_case.execute(ip_address="10.0.0.5", username="admin", password="secret")
