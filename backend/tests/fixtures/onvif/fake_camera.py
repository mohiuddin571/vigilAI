"""A fixture-driven stand-in for `onvif.ONVIFCamera` (T-037).

Rather than a byte-level SOAP/WSDL simulator, `OnvifCameraGateway` accepts an
injectable client factory; these fakes are built from recorded-shape JSON
fixtures (`device_information.json`, `profiles.json`) mirroring real
`GetDeviceInformation`/`GetProfiles` response attribute shapes, confirmed
against the actual ONVIF WSDL/XSD shipped by `onvif-zeep-async`.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_FIXTURES_DIR = Path(__file__).parent


def _to_namespace(data: Any) -> Any:
    if isinstance(data, dict):
        return SimpleNamespace(**{key: _to_namespace(value) for key, value in data.items()})
    if isinstance(data, list):
        return [_to_namespace(item) for item in data]
    return data


def load_device_information() -> Any:
    raw = json.loads((_FIXTURES_DIR / "device_information.json").read_text())
    return _to_namespace(raw)


def load_profiles() -> list[Any]:
    raw = json.loads((_FIXTURES_DIR / "profiles.json").read_text())
    return [_to_namespace(item) for item in raw]


def load_video_encoder_configurations() -> dict[str, Any]:
    raw = json.loads((_FIXTURES_DIR / "video_encoder_configurations.json").read_text())
    return {token: _to_namespace(value) for token, value in raw.items()}


def load_video_encoder_configuration_options() -> dict[str, Any]:
    raw = json.loads((_FIXTURES_DIR / "video_encoder_configuration_options.json").read_text())
    return {token: _to_namespace(value) for token, value in raw.items()}


class _FakeDeviceManagementService:
    def __init__(self, device_information: Any) -> None:
        self._device_information = device_information

    async def GetDeviceInformation(self) -> Any:
        return self._device_information


class _FakeMediaService:
    """Stateful enough that `SetVideoEncoderConfiguration` is reflected by a
    subsequent `GetVideoEncoderConfiguration`/`GetProfiles` call, matching the
    real camera's read-your-writes behavior M4's acceptance criteria depend on.

    Every multi-field method takes a single positional `params` dict, matching
    `onvif.ONVIFService.__getattr__`'s real `wrapped(params=None)` contract
    (confirmed against real hardware — docs/TECHNICAL_DECISIONS.md TD-22) —
    not separate top-level kwargs, which the real library rejects even though
    an earlier, kwargs-shaped version of this fake didn't catch that mismatch.
    """

    def __init__(
        self,
        profiles: list[Any],
        video_encoder_configs: dict[str, Any],
        video_encoder_options: dict[str, Any],
        stream_uri: str = "rtsp://camera.invalid:554/stream1",
    ) -> None:
        self._profiles = profiles
        self._video_encoder_configs = video_encoder_configs
        self._video_encoder_options = video_encoder_options
        self._stream_uri = stream_uri

    async def GetProfiles(self) -> list[Any]:
        return self._profiles

    async def GetStreamUri(self, params: dict[str, Any]) -> Any:
        return SimpleNamespace(Uri=self._stream_uri)

    async def GetVideoEncoderConfiguration(self, params: dict[str, Any]) -> Any:
        return self._video_encoder_configs[params["ConfigurationToken"]]

    async def GetVideoEncoderConfigurationOptions(self, params: dict[str, Any]) -> Any:
        return self._video_encoder_options[str(params["ConfigurationToken"])]

    async def SetVideoEncoderConfiguration(self, params: dict[str, Any]) -> None:
        configuration = params["Configuration"]
        token = configuration.token
        self._video_encoder_configs[token] = configuration
        for profile in self._profiles:
            enc_config = getattr(profile, "VideoEncoderConfiguration", None)
            if enc_config is not None and getattr(enc_config, "token", None) == token:
                profile.VideoEncoderConfiguration = configuration


class FakeOnvifCamera:
    """Drop-in replacement for `onvif.ONVIFCamera`'s constructor + calls this gateway uses."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        passwd: str,
        *,
        adjust_time: bool = False,
        nat_override: bool = False,
        device_information: Any | None = None,
        profiles: list[Any] | None = None,
        video_encoder_configs: dict[str, Any] | None = None,
        video_encoder_options: dict[str, Any] | None = None,
        stream_uri: str = "rtsp://camera.invalid:554/stream1",
        fail_with: Exception | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.adjust_time = adjust_time
        self.nat_override = nat_override
        self._device_information = (
            device_information if device_information is not None else load_device_information()
        )
        self._profiles = profiles if profiles is not None else load_profiles()
        self._video_encoder_configs = (
            video_encoder_configs
            if video_encoder_configs is not None
            else load_video_encoder_configurations()
        )
        self._video_encoder_options = (
            video_encoder_options
            if video_encoder_options is not None
            else load_video_encoder_configuration_options()
        )
        self._stream_uri = stream_uri
        self._fail_with = fail_with

    async def update_xaddrs(self) -> None:
        if self._fail_with is not None:
            raise self._fail_with

    async def create_devicemgmt_service(self) -> _FakeDeviceManagementService:
        return _FakeDeviceManagementService(self._device_information)

    async def create_media_service(self) -> _FakeMediaService:
        return _FakeMediaService(
            self._profiles,
            self._video_encoder_configs,
            self._video_encoder_options,
            self._stream_uri,
        )

    async def close(self) -> None:
        pass
