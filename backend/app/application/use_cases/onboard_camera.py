from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.camera import Camera


class OnboardCameraUseCase:
    """Authenticate against a camera over ONVIF and persist it with its stream profiles.

    Preconditions: `ip_address`/`username`/`password` identify a camera reachable
    on the network.

    Postconditions: a `Camera` (with its discovered `StreamProfile`s) is persisted
    via `camera_repository` and returned.

    Raises:
        CameraAuthenticationError: the camera rejected the supplied credentials.
        CameraUnreachableError: the camera could not be reached over the network.
    """

    def __init__(
        self, camera_gateway: ICameraGateway, camera_repository: ICameraRepository
    ) -> None:
        self._camera_gateway = camera_gateway
        self._camera_repository = camera_repository

    async def execute(
        self,
        ip_address: str,
        username: str,
        password: str,
        port: int = 80,
        rtsp_url_override: str | None = None,
    ) -> Camera:
        try:
            await self._camera_gateway.connect(ip_address, username, password, port)
            device_info = await self._camera_gateway.get_device_info()
            profiles = await self._camera_gateway.get_profiles()
        finally:
            await self._camera_gateway.disconnect()

        name = ip_address
        if device_info.manufacturer and device_info.model:
            name = f"{device_info.manufacturer} {device_info.model}"

        camera = Camera(
            name=name,
            ip_address=ip_address,
            username=username,
            port=port,
            password=password,
            rtsp_url_override=rtsp_url_override,
            manufacturer=device_info.manufacturer,
            model=device_info.model,
            firmware_version=device_info.firmware_version,
            stream_profiles=profiles,
            is_online=True,
        )
        await self._camera_repository.add(camera)
        return camera
