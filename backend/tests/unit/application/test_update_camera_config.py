from uuid import UUID

import pytest

from app.application.dto.camera_config import CameraConfigUpdate
from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraNotFoundError, UnsupportedConfigurationError
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities


def _profile(**overrides: object) -> StreamProfile:
    defaults: dict[str, object] = {
        "name": "MainStream",
        "resolution": Resolution(width=1920, height=1080),
        "codec": Codec.H264,
        "bitrate": BitrateKbps(value=4096),
        "fps": 25,
        "onvif_token": "Profile_1",
    }
    defaults.update(overrides)
    return StreamProfile(**defaults)  # type: ignore[arg-type]


def _capabilities() -> VideoEncoderCapabilities:
    return VideoEncoderCapabilities(
        codec=Codec.H264,
        resolutions=[Resolution(width=1920, height=1080), Resolution(width=1280, height=720)],
        fps_min=1,
        fps_max=30,
        bitrate_min_kbps=512,
        bitrate_max_kbps=8192,
    )


class FakeCameraGateway(ICameraGateway):
    """Simulates a camera that actually applies a successful Set, so the
    subsequent live read reflects it — mirrors real ONVIF read-your-writes
    behavior that AC #2 depends on.
    """

    def __init__(
        self,
        *,
        profile: StreamProfile,
        capabilities: VideoEncoderCapabilities,
        fail_set_with: Exception | None = None,
    ) -> None:
        self._profile = profile
        self._capabilities = capabilities
        self._fail_set_with = fail_set_with
        self.connected_with: tuple[str, str, str, int] | None = None
        self.disconnected = False
        self.set_calls: list[tuple[str, StreamProfile]] = []

    async def connect(self, ip_address: str, username: str, password: str, port: int = 80) -> None:
        self.connected_with = (ip_address, username, password, port)

    async def get_device_info(self) -> Camera:
        raise NotImplementedError

    async def get_profiles(self) -> list[StreamProfile]:
        raise NotImplementedError

    async def get_video_encoder_configuration(self, profile_id: str) -> StreamProfile:
        return self._profile

    async def set_video_encoder_configuration(
        self, profile_id: str, profile: StreamProfile
    ) -> None:
        self.set_calls.append((profile_id, profile))
        if self._fail_set_with is not None:
            raise self._fail_set_with
        self._profile = profile

    async def get_video_encoder_configuration_options(
        self, profile_id: str
    ) -> VideoEncoderCapabilities:
        return self._capabilities

    async def get_stream_uri(self, profile_id: str) -> str:
        raise NotImplementedError

    async def disconnect(self) -> None:
        self.disconnected = True


class FakeCameraRepository(ICameraRepository):
    def __init__(self, cameras: list[Camera] | None = None) -> None:
        self.cameras: dict[UUID, Camera] = {c.id: c for c in (cameras or [])}
        self.update_calls: list[Camera] = []

    async def add(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera

    async def get(self, camera_id: UUID) -> Camera | None:
        return self.cameras.get(camera_id)

    async def list(self) -> list[Camera]:
        return list(self.cameras.values())

    async def update(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera
        self.update_calls.append(camera)


def _camera(**overrides: object) -> Camera:
    defaults: dict[str, object] = {
        "name": "Cam-1",
        "ip_address": "10.0.0.5",
        "username": "admin",
        "password": "secret",
        "port": 8000,
        "stream_profiles": [_profile()],
    }
    defaults.update(overrides)
    return Camera(**defaults)  # type: ignore[arg-type]


async def test_update_camera_config_applies_partial_update_and_persists() -> None:
    camera = _camera()
    original_profile_id = camera.stream_profiles[0].id
    gateway = FakeCameraGateway(profile=_profile(), capabilities=_capabilities())
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraConfigUseCase(gateway, repository)

    result = await use_case.execute(
        camera.id, "Profile_1", CameraConfigUpdate(bitrate=BitrateKbps(value=2048))
    )

    assert result.bitrate == BitrateKbps(value=2048)
    # Unspecified fields keep their current live value.
    assert result.resolution == Resolution(width=1920, height=1080)
    assert result.fps == 25
    # Our own internal identity is preserved across the update.
    assert result.id == original_profile_id
    assert result.onvif_token == "Profile_1"

    persisted = repository.cameras[camera.id]
    assert persisted.stream_profiles[0].bitrate == BitrateKbps(value=2048)
    assert gateway.disconnected is True

    sent_profile_id, sent_profile = gateway.set_calls[0]
    assert sent_profile_id == "Profile_1"
    assert sent_profile.bitrate == BitrateKbps(value=2048)
    assert sent_profile.resolution == Resolution(width=1920, height=1080)


async def test_update_camera_config_raises_when_camera_not_found() -> None:
    gateway = FakeCameraGateway(profile=_profile(), capabilities=_capabilities())
    repository = FakeCameraRepository([])
    use_case = UpdateCameraConfigUseCase(gateway, repository)

    with pytest.raises(CameraNotFoundError):
        await use_case.execute(UUID(int=0), "Profile_1", CameraConfigUpdate())


async def test_update_camera_config_raises_when_profile_not_found() -> None:
    camera = _camera()
    gateway = FakeCameraGateway(profile=_profile(), capabilities=_capabilities())
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraConfigUseCase(gateway, repository)

    with pytest.raises(CameraNotFoundError):
        await use_case.execute(camera.id, "NoSuchProfile", CameraConfigUpdate())


async def test_update_camera_config_propagates_unsupported_change_without_persisting() -> None:
    camera = _camera()
    gateway = FakeCameraGateway(
        profile=_profile(),
        capabilities=_capabilities(),
        fail_set_with=UnsupportedConfigurationError("camera rejected the change"),
    )
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraConfigUseCase(gateway, repository)

    with pytest.raises(UnsupportedConfigurationError):
        await use_case.execute(camera.id, "Profile_1", CameraConfigUpdate(codec=Codec.MJPEG))

    assert repository.update_calls == []
    assert gateway.disconnected is True
