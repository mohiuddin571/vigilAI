from types import SimpleNamespace

from app.domain.exceptions import CameraAuthenticationError, CameraUnreachableError
from app.domain.value_objects.codec import Codec
from app.infrastructure.onvif.mappers import (
    classify_onvif_error,
    map_codec,
    map_device_info,
    map_profile,
)


def _profile(
    *,
    name: str | None = "MainStream",
    token: str | None = "Profile_1",
    encoding: str = "H264",
    width: int = 1920,
    height: int = 1080,
    bitrate: int = 4096,
    fps: int = 25,
    has_encoder_config: bool = True,
    has_rate_control: bool = True,
) -> SimpleNamespace:
    if not has_encoder_config:
        return SimpleNamespace(Name=name, token=token)
    rate_control = (
        SimpleNamespace(FrameRateLimit=fps, EncodingInterval=1, BitrateLimit=bitrate)
        if has_rate_control
        else None
    )
    return SimpleNamespace(
        Name=name,
        token=token,
        VideoEncoderConfiguration=SimpleNamespace(
            Encoding=encoding,
            Resolution=SimpleNamespace(Width=width, Height=height),
            RateControl=rate_control,
        ),
    )


def test_map_device_info_carries_manufacturer_model_firmware() -> None:
    info = SimpleNamespace(Manufacturer="Acme", Model="AV-1", FirmwareVersion="1.0")
    camera = map_device_info("10.0.0.5", "admin", info)
    assert camera.manufacturer == "Acme"
    assert camera.model == "AV-1"
    assert camera.firmware_version == "1.0"
    assert camera.ip_address == "10.0.0.5"


def test_map_codec_known_values() -> None:
    assert map_codec("H264") == Codec.H264
    assert map_codec("JPEG") == Codec.MJPEG
    assert map_codec("MPEG4") == Codec.MPEG4


def test_map_codec_unknown_value_returns_none() -> None:
    assert map_codec("VP9") is None


def test_map_profile_success() -> None:
    profile = map_profile(_profile())
    assert profile is not None
    assert profile.name == "MainStream"
    assert profile.onvif_token == "Profile_1"
    assert profile.resolution.width == 1920
    assert profile.resolution.height == 1080
    assert profile.codec == Codec.H264
    assert profile.bitrate.value == 4096
    assert profile.fps == 25


def test_map_profile_skips_profile_missing_encoder_config() -> None:
    assert map_profile(_profile(has_encoder_config=False)) is None


def test_map_profile_skips_profile_missing_rate_control() -> None:
    assert map_profile(_profile(has_rate_control=False)) is None


def test_map_profile_skips_unknown_codec() -> None:
    assert map_profile(_profile(encoding="VP9")) is None


def test_classify_onvif_error_auth_hint_in_message() -> None:
    error = classify_onvif_error(Exception("Sender NotAuthorized: bad credentials"))
    assert isinstance(error, CameraAuthenticationError)


def test_classify_onvif_error_onvif_auth_error_type() -> None:
    class ONVIFAuthError(Exception):
        pass

    error = classify_onvif_error(ONVIFAuthError("401"))
    assert isinstance(error, CameraAuthenticationError)


def test_classify_onvif_error_falls_back_to_unreachable() -> None:
    error = classify_onvif_error(TimeoutError("connection timed out"))
    assert isinstance(error, CameraUnreachableError)
