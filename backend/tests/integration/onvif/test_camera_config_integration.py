"""T-040/T-041/T-042: exercises `OnvifCameraGateway`'s encoder-config methods and
the two M4 use cases end-to-end against the fixture-driven fake ONVIF client
and a real `SqlCameraRepository` (temp SQLite), proving:

- GET is always a live read (AC #1).
- A supported PATCH is reflected on the next GET, including after reopening
  the repository (AC #2, and the use case's persistence postcondition).
- An unsupported field/value raises a typed `UnsupportedConfigurationError`
  and does not persist (AC #3).
"""

import functools
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

from app.application.dto.camera_config import CameraConfigUpdate
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.domain.entities.camera import Camera
from app.domain.exceptions import UnsupportedConfigurationError
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher
from tests.fixtures.onvif.fake_camera import (
    FakeOnvifCamera,
    load_profiles,
    load_video_encoder_configuration_options,
    load_video_encoder_configurations,
)


def _shared_camera_client_factory() -> Callable[..., Any]:
    """A `client_factory` bound to one shared, mutable in-memory camera state.

    `OnvifCameraGateway.connect()` constructs a fresh `FakeOnvifCamera` on
    every call (mirroring a real camera's request/response cycle) — this
    binds every such construction within a test to the *same* profiles/
    encoder-config/options dicts, so a `SetVideoEncoderConfiguration` from one
    "connection" is visible to the next, exactly like a real camera's
    persisted configuration survives a reconnect.
    """
    return functools.partial(
        FakeOnvifCamera,
        profiles=load_profiles(),
        video_encoder_configs=load_video_encoder_configurations(),
        video_encoder_options=load_video_encoder_configuration_options(),
    )


async def _open_repository(db_path: Path, encryption_key: str) -> SqlCameraRepository:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    return SqlCameraRepository(build_session_factory(engine), CredentialCipher(encryption_key))


async def _onboard(repository: SqlCameraRepository, client_factory: Callable[..., Any]) -> Camera:
    gateway = OnvifCameraGateway(client_factory=client_factory)
    return await OnboardCameraUseCase(gateway, repository).execute(
        ip_address="10.0.0.5", username="admin", password="s3cret-pass", port=8000
    )


async def test_get_camera_config_returns_live_values_and_capabilities(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "cameras.db", Fernet.generate_key().decode())
    client_factory = _shared_camera_client_factory()
    camera = await _onboard(repository, client_factory)

    gateway = OnvifCameraGateway(client_factory=client_factory)
    dto = await GetCameraConfigUseCase(gateway, repository).execute(camera.id, "Profile_1")

    assert dto.profile.resolution == Resolution(width=1920, height=1080)
    assert dto.profile.codec == Codec.H264
    assert dto.profile.bitrate == BitrateKbps(value=4096)
    assert dto.profile.fps == 25
    assert dto.capabilities.codec == Codec.H264
    assert Resolution(width=1280, height=720) in dto.capabilities.resolutions
    assert dto.capabilities.bitrate_min_kbps == 512
    assert dto.capabilities.bitrate_max_kbps == 8192


async def test_patch_supported_bitrate_is_reflected_on_next_get_and_persists(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cameras.db"
    encryption_key = Fernet.generate_key().decode()
    repository = await _open_repository(db_path, encryption_key)
    client_factory = _shared_camera_client_factory()
    camera = await _onboard(repository, client_factory)

    gateway = OnvifCameraGateway(client_factory=client_factory)
    updated = await UpdateCameraConfigUseCase(gateway, repository).execute(
        camera.id, "Profile_1", CameraConfigUpdate(bitrate=BitrateKbps(value=2048))
    )
    assert updated.bitrate == BitrateKbps(value=2048)

    # Next GET, through a fresh gateway connection, reflects the change.
    get_gateway = OnvifCameraGateway(client_factory=client_factory)
    dto = await GetCameraConfigUseCase(get_gateway, repository).execute(camera.id, "Profile_1")
    assert dto.profile.bitrate == BitrateKbps(value=2048)
    # Other fields are untouched.
    assert dto.profile.resolution == Resolution(width=1920, height=1080)
    assert dto.profile.fps == 25

    # And it's actually persisted, surviving an API restart.
    restarted_repository = await _open_repository(db_path, encryption_key)
    restarted_camera = await restarted_repository.get(camera.id)
    assert restarted_camera is not None
    persisted_profile = next(
        p for p in restarted_camera.stream_profiles if p.onvif_token == "Profile_1"
    )
    assert persisted_profile.bitrate == BitrateKbps(value=2048)


async def test_patch_unsupported_resolution_raises_typed_error_and_does_not_persist(
    tmp_path: Path,
) -> None:
    repository = await _open_repository(tmp_path / "cameras.db", Fernet.generate_key().decode())
    client_factory = _shared_camera_client_factory()
    camera = await _onboard(repository, client_factory)
    original_bitrate = next(
        p for p in camera.stream_profiles if p.onvif_token == "Profile_1"
    ).bitrate

    gateway = OnvifCameraGateway(client_factory=client_factory)
    with pytest.raises(UnsupportedConfigurationError):
        await UpdateCameraConfigUseCase(gateway, repository).execute(
            camera.id,
            "Profile_1",
            CameraConfigUpdate(resolution=Resolution(width=99, height=99)),
        )

    persisted = await repository.get(camera.id)
    assert persisted is not None
    persisted_profile = next(p for p in persisted.stream_profiles if p.onvif_token == "Profile_1")
    assert persisted_profile.bitrate == original_bitrate


async def test_patch_codec_change_raises_typed_error(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "cameras.db", Fernet.generate_key().decode())
    client_factory = _shared_camera_client_factory()
    camera = await _onboard(repository, client_factory)

    gateway = OnvifCameraGateway(client_factory=client_factory)
    with pytest.raises(UnsupportedConfigurationError):
        await UpdateCameraConfigUseCase(gateway, repository).execute(
            camera.id, "Profile_1", CameraConfigUpdate(codec=Codec.MJPEG)
        )


async def test_patch_bitrate_out_of_range_raises_typed_error(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "cameras.db", Fernet.generate_key().decode())
    client_factory = _shared_camera_client_factory()
    camera = await _onboard(repository, client_factory)

    gateway = OnvifCameraGateway(client_factory=client_factory)
    with pytest.raises(UnsupportedConfigurationError):
        await UpdateCameraConfigUseCase(gateway, repository).execute(
            camera.id, "Profile_1", CameraConfigUpdate(bitrate=BitrateKbps(value=99_999))
        )


async def test_patch_profile_without_reported_bitrate_range_accepts_any_bitrate(
    tmp_path: Path,
) -> None:
    """Profile_2/VideoEncoderToken_2 (JPEG) has no `Extension.JPEG.BitrateRange`
    in the fixture — this system has no reported bound to pre-validate
    against, so it defers to the camera's own acceptance."""
    repository = await _open_repository(tmp_path / "cameras.db", Fernet.generate_key().decode())
    client_factory = _shared_camera_client_factory()
    camera = await _onboard(repository, client_factory)

    gateway = OnvifCameraGateway(client_factory=client_factory)
    updated = await UpdateCameraConfigUseCase(gateway, repository).execute(
        camera.id, "Profile_2", CameraConfigUpdate(bitrate=BitrateKbps(value=999_999))
    )
    assert updated.bitrate == BitrateKbps(value=999_999)
