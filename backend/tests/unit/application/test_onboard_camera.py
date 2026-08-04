from uuid import UUID

import pytest

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraAuthenticationError
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities


class FakeCameraGateway(ICameraGateway):
    """No real I/O — a hand-written double for `ICameraGateway`."""

    def __init__(self, *, fail_connect: Exception | None = None) -> None:
        self._fail_connect = fail_connect
        self.connected_with: tuple[str, str, str, int] | None = None
        self.disconnected = False

    async def connect(self, ip_address: str, username: str, password: str, port: int = 80) -> None:
        self.connected_with = (ip_address, username, password, port)
        if self._fail_connect is not None:
            raise self._fail_connect

    async def get_device_info(self) -> Camera:
        return Camera(
            name="placeholder",
            ip_address="10.0.0.5",
            username="admin",
            manufacturer="Acme",
            model="AV-1",
            firmware_version="1.0",
        )

    async def get_profiles(self) -> list[StreamProfile]:
        return [
            StreamProfile(
                name="Main",
                resolution=Resolution(width=1920, height=1080),
                codec=Codec.H264,
                bitrate=BitrateKbps(value=4096),
                fps=25,
                onvif_token="Profile_1",
            )
        ]

    async def get_video_encoder_configuration(self, profile_id: str) -> StreamProfile:
        raise NotImplementedError

    async def set_video_encoder_configuration(
        self, profile_id: str, profile: StreamProfile
    ) -> None:
        raise NotImplementedError

    async def get_video_encoder_configuration_options(
        self, profile_id: str
    ) -> VideoEncoderCapabilities:
        raise NotImplementedError

    async def get_stream_uri(self, profile_id: str) -> str:
        raise NotImplementedError

    async def disconnect(self) -> None:
        self.disconnected = True


class FakeCameraRepository(ICameraRepository):
    def __init__(self) -> None:
        self.cameras: dict[UUID, Camera] = {}

    async def add(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera

    async def get(self, camera_id: UUID) -> Camera | None:
        return self.cameras.get(camera_id)

    async def list(self) -> list[Camera]:
        return list(self.cameras.values())

    async def update(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera


async def test_onboard_camera_persists_device_info_and_profiles() -> None:
    gateway = FakeCameraGateway()
    repository = FakeCameraRepository()
    use_case = OnboardCameraUseCase(gateway, repository)

    camera = await use_case.execute(
        ip_address="10.0.0.5", username="admin", password="secret", port=8000
    )

    assert camera.manufacturer == "Acme"
    assert camera.name == "Acme AV-1"
    assert camera.is_online is True
    assert camera.password == "secret"
    assert len(camera.stream_profiles) == 1
    assert repository.cameras[camera.id] is camera
    assert gateway.connected_with == ("10.0.0.5", "admin", "secret", 8000)
    assert gateway.disconnected is True


async def test_onboard_camera_falls_back_to_ip_when_no_device_info() -> None:
    class NoInfoGateway(FakeCameraGateway):
        async def get_device_info(self) -> Camera:
            return Camera(name="placeholder", ip_address="10.0.0.5", username="admin")

    use_case = OnboardCameraUseCase(NoInfoGateway(), FakeCameraRepository())
    camera = await use_case.execute(ip_address="10.0.0.5", username="admin", password="secret")

    assert camera.name == "10.0.0.5"


async def test_onboard_camera_propagates_authentication_failure_without_persisting() -> None:
    gateway = FakeCameraGateway(fail_connect=CameraAuthenticationError("bad credentials"))
    repository = FakeCameraRepository()
    use_case = OnboardCameraUseCase(gateway, repository)

    with pytest.raises(CameraAuthenticationError):
        await use_case.execute(ip_address="10.0.0.5", username="admin", password="wrong")

    assert repository.cameras == {}
    assert gateway.disconnected is True
