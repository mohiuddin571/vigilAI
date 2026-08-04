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


class _FakeDeviceManagementService:
    def __init__(self, device_information: Any) -> None:
        self._device_information = device_information

    async def GetDeviceInformation(self) -> Any:
        return self._device_information


class _FakeMediaService:
    def __init__(self, profiles: list[Any]) -> None:
        self._profiles = profiles

    async def GetProfiles(self) -> list[Any]:
        return self._profiles


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
        device_information: Any | None = None,
        profiles: list[Any] | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self._device_information = (
            device_information if device_information is not None else load_device_information()
        )
        self._profiles = profiles if profiles is not None else load_profiles()
        self._fail_with = fail_with

    async def update_xaddrs(self) -> None:
        if self._fail_with is not None:
            raise self._fail_with

    async def create_devicemgmt_service(self) -> _FakeDeviceManagementService:
        return _FakeDeviceManagementService(self._device_information)

    async def create_media_service(self) -> _FakeMediaService:
        return _FakeMediaService(self._profiles)

    async def close(self) -> None:
        pass
