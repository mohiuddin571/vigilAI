from collections.abc import Callable
from typing import Any

from onvif import ONVIFCamera

from app.application.ports.camera_gateway import ICameraGateway
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraUnreachableError
from app.infrastructure.onvif.mappers import classify_onvif_error, map_device_info, map_profile


class OnvifCameraGateway(ICameraGateway):
    """`ICameraGateway` implementation wrapping `onvif-zeep-async` (TD-03).

    `connect`, `get_device_info`, and `get_profiles` have real logic per M3;
    `get_video_encoder_configuration`/`set_video_encoder_configuration` (M4)
    and `get_stream_uri` (M5) are stub bodies only.

    `client_factory` defaults to the real `ONVIFCamera` constructor and exists
    so integration tests can inject a fixture-driven fake without a real
    camera or a protocol-level SOAP simulator (see docs/TASK_BACKLOG.md T-037).
    """

    def __init__(self, client_factory: Callable[..., Any] = ONVIFCamera) -> None:
        self._client_factory = client_factory
        self._camera: Any = None
        self._connected = False
        self._ip_address = ""
        self._username = ""

    async def connect(self, ip_address: str, username: str, password: str, port: int = 80) -> None:
        self._ip_address = ip_address
        self._username = username
        # Set eagerly, before authenticating: the client may already hold an
        # open aiohttp session by the time `update_xaddrs()` fails, so
        # `disconnect()` needs a reference to clean it up either way.
        #
        # adjust_time=True: WS-Security digest auth is timestamp-based, so
        # clock skew between this host and the camera makes even a *correct*
        # password fail the digest check — the camera's own SOAP fault for
        # this is indistinguishable from a real bad password (confirmed
        # against real hardware: a Matrix MIDR20FL28CWS returned a "Password
        # Mismatch" fault for valid credentials until this flag was added).
        # This has the client measure and compensate for the offset first.
        self._camera = self._client_factory(ip_address, port, username, password, adjust_time=True)
        try:
            await self._camera.update_xaddrs()
        except Exception as exc:
            raise classify_onvif_error(exc) from exc
        self._connected = True

    async def get_device_info(self) -> Camera:
        self._require_connected()
        try:
            devicemgmt = await self._camera.create_devicemgmt_service()
            info = await devicemgmt.GetDeviceInformation()
        except Exception as exc:
            raise classify_onvif_error(exc) from exc
        return map_device_info(self._ip_address, self._username, info)

    async def get_profiles(self) -> list[StreamProfile]:
        self._require_connected()
        try:
            media = await self._camera.create_media_service()
            profiles = await media.GetProfiles()
        except Exception as exc:
            raise classify_onvif_error(exc) from exc
        return [mapped for p in profiles if (mapped := map_profile(p)) is not None]

    async def get_video_encoder_configuration(self, profile_id: str) -> StreamProfile:
        raise NotImplementedError

    async def set_video_encoder_configuration(
        self, profile_id: str, profile: StreamProfile
    ) -> None:
        raise NotImplementedError

    async def get_stream_uri(self, profile_id: str) -> str:
        raise NotImplementedError

    async def disconnect(self) -> None:
        if self._camera is not None:
            await self._camera.close()
            self._camera = None
            self._connected = False

    def _require_connected(self) -> None:
        if not self._connected:
            raise CameraUnreachableError("connect() must succeed before calling the camera")
