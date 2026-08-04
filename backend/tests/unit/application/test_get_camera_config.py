from uuid import UUID

import pytest

from app.application.dto.camera_config import CameraConfigDTO
from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraNotFoundError
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
        resolutions=[Resolution(width=1920, height=1080)],
        fps_min=1,
        fps_max=30,
        bitrate_min_kbps=512,
        bitrate_max_kbps=8192,
    )


class FakeCameraGateway(ICameraGateway):
    def __init__(self, *, profile: StreamProfile, capabilities: VideoEncoderCapabilities) -> None:
        self._profile = profile
        self._capabilities = capabilities
        self.connected_with: tuple[str, str, str, int] | None = None
        self.disconnected = False

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
        raise NotImplementedError

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

    async def add(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera

    async def get(self, camera_id: UUID) -> Camera | None:
        return self.cameras.get(camera_id)

    async def list(self) -> list[Camera]:
        return list(self.cameras.values())

    async def update(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera


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


async def test_get_camera_config_returns_live_profile_and_capabilities() -> None:
    camera = _camera()
    gateway = FakeCameraGateway(profile=_profile(), capabilities=_capabilities())
    repository = FakeCameraRepository([camera])
    use_case = GetCameraConfigUseCase(gateway, repository)

    result = await use_case.execute(camera.id, "Profile_1")

    assert isinstance(result, CameraConfigDTO)
    assert result.profile.bitrate == BitrateKbps(value=4096)
    assert result.capabilities.codec == Codec.H264
    assert gateway.connected_with == ("10.0.0.5", "admin", "secret", 8000)
    assert gateway.disconnected is True


async def test_get_camera_config_raises_when_camera_not_found() -> None:
    gateway = FakeCameraGateway(profile=_profile(), capabilities=_capabilities())
    repository = FakeCameraRepository([])
    use_case = GetCameraConfigUseCase(gateway, repository)

    with pytest.raises(CameraNotFoundError):
        await use_case.execute(UUID(int=0), "Profile_1")


async def test_get_camera_config_raises_when_profile_not_found() -> None:
    camera = _camera()
    gateway = FakeCameraGateway(profile=_profile(), capabilities=_capabilities())
    repository = FakeCameraRepository([camera])
    use_case = GetCameraConfigUseCase(gateway, repository)

    with pytest.raises(CameraNotFoundError):
        await use_case.execute(camera.id, "NoSuchProfile")
