from collections.abc import Callable
from typing import Any

from onvif import ONVIFCamera

from app.application.ports.camera_gateway import ICameraGateway
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import (
    CameraAuthenticationError,
    CameraUnreachableError,
    DomainError,
    UnsupportedConfigurationError,
)
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities
from app.infrastructure.onvif import encoder_config
from app.infrastructure.onvif.mappers import (
    classify_onvif_error,
    map_codec,
    map_device_info,
    map_profile,
)


class OnvifCameraGateway(ICameraGateway):
    """`ICameraGateway` implementation wrapping `onvif-zeep-async` (TD-03).

    `connect`, `get_device_info`, `get_profiles` (M3);
    `get_video_encoder_configuration`/`set_video_encoder_configuration`/
    `get_video_encoder_configuration_options` (M4); and `get_stream_uri`
    (M5, resolving `GetStreamUri` for RTSP live-view) all have real logic.

    `client_factory` defaults to the real `ONVIFCamera` constructor and exists
    so integration tests can inject a fixture-driven fake without a real
    camera or a protocol-level SOAP simulator (see docs/TASK_BACKLOG.md T-037).

    Every multi-field SOAP call below passes its parameters as a single dict
    positional argument (e.g. `media.GetStreamUri({"StreamSetup": ..., "ProfileToken": ...})`),
    never as separate top-level kwargs — `onvif.ONVIFService.__getattr__`'s
    `wrapped(params=None)` only accepts one `params` argument itself (which it
    then unpacks into the underlying SOAP call), so `media.Op(A=..., B=...)`
    fails with "unexpected keyword argument" against the real library even
    though it type-checks fine against a hand-written fake. Confirmed against
    real hardware (docs/TECHNICAL_DECISIONS.md TD-22) — this is exactly the gap
    TD-18 flagged as a limitation of fixture-only ONVIF testing.
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
        # Assessment cameras may be reachable through a public port-forward
        # while advertising their private-LAN XAddrs in GetServices or
        # GetCapabilities.  Tell the ONVIF client to retain the configured
        # host/port for those service URLs instead of following an unreachable
        # advertised LAN address.  This is a no-op for a direct LAN connection.
        self._camera = self._client_factory(
            ip_address,
            port,
            username,
            password,
            adjust_time=True,
            nat_override=True,
        )
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
        self._require_connected()
        try:
            media = await self._camera.create_media_service()
            config_token = await encoder_config.resolve_video_encoder_configuration_token(
                media, profile_id
            )
            raw_config = await media.GetVideoEncoderConfiguration(
                {"ConfigurationToken": config_token}
            )
        except DomainError:
            raise
        except Exception as exc:
            raise classify_onvif_error(exc) from exc

        mapped = encoder_config.map_video_encoder_configuration(raw_config)
        if mapped is None:
            raise UnsupportedConfigurationError(
                f"Camera reported an unrecognized encoding for profile {profile_id!r} "
                "(see docs/TECHNICAL_DECISIONS.md TD-18)"
            )
        return mapped

    async def set_video_encoder_configuration(
        self, profile_id: str, profile: StreamProfile
    ) -> None:
        self._require_connected()
        try:
            media = await self._camera.create_media_service()
            config_token = await encoder_config.resolve_video_encoder_configuration_token(
                media, profile_id
            )
            raw_config = await media.GetVideoEncoderConfiguration(
                {"ConfigurationToken": config_token}
            )
            raw_options = await media.GetVideoEncoderConfigurationOptions(
                {"ConfigurationToken": config_token, "ProfileToken": profile_id}
            )
        except DomainError:
            raise
        except Exception as exc:
            raise classify_onvif_error(exc) from exc

        current_codec = map_codec(getattr(raw_config, "Encoding", ""))
        if current_codec is None:
            raise UnsupportedConfigurationError(
                f"Camera reported an unrecognized encoding for profile {profile_id!r}; "
                "refusing to update it (see docs/TECHNICAL_DECISIONS.md TD-18)"
            )
        capabilities = encoder_config.map_video_encoder_configuration_options(
            raw_options, current_codec
        )
        encoder_config.validate_requested_configuration(profile, capabilities)
        encoder_config.apply_stream_profile_to_raw_configuration(raw_config, profile)

        try:
            await media.SetVideoEncoderConfiguration(
                {"Configuration": raw_config, "ForcePersistence": True}
            )
        except Exception as exc:
            # Our own pre-validation above should catch most rejections, but the
            # camera is the final authority — never let a raw SOAP fault escape.
            # A fault classified as an auth/permission failure (e.g. the ONVIF
            # account lacks privilege to change encoder settings) is reported
            # as such rather than folded into a generic 422.
            classified = classify_onvif_error(exc)
            if isinstance(classified, CameraAuthenticationError):
                raise classified from exc
            raise UnsupportedConfigurationError(
                str(exc) or "Camera rejected the requested configuration"
            ) from exc

    async def get_video_encoder_configuration_options(
        self, profile_id: str
    ) -> VideoEncoderCapabilities:
        self._require_connected()
        try:
            media = await self._camera.create_media_service()
            config_token = await encoder_config.resolve_video_encoder_configuration_token(
                media, profile_id
            )
            raw_config = await media.GetVideoEncoderConfiguration(
                {"ConfigurationToken": config_token}
            )
            raw_options = await media.GetVideoEncoderConfigurationOptions(
                {"ConfigurationToken": config_token, "ProfileToken": profile_id}
            )
        except DomainError:
            raise
        except Exception as exc:
            raise classify_onvif_error(exc) from exc

        codec = map_codec(getattr(raw_config, "Encoding", ""))
        if codec is None:
            raise UnsupportedConfigurationError(
                f"Camera reported an unrecognized encoding for profile {profile_id!r} "
                "(see docs/TECHNICAL_DECISIONS.md TD-18)"
            )
        return encoder_config.map_video_encoder_configuration_options(raw_options, codec)

    async def get_stream_uri(self, profile_id: str) -> str:
        self._require_connected()
        try:
            media = await self._camera.create_media_service()
            response = await media.GetStreamUri(
                {
                    "StreamSetup": {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}},
                    "ProfileToken": profile_id,
                }
            )
        except Exception as exc:
            raise classify_onvif_error(exc) from exc

        uri = getattr(response, "Uri", None)
        if not uri:
            raise CameraUnreachableError(
                f"Camera did not return a stream URI for profile {profile_id!r}"
            )
        return str(uri)

    async def disconnect(self) -> None:
        if self._camera is not None:
            await self._camera.close()
            self._camera = None
            self._connected = False

    def _require_connected(self) -> None:
        if not self._connected:
            raise CameraUnreachableError("connect() must succeed before calling the camera")
