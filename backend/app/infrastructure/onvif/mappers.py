from typing import Any

import structlog

from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraAuthenticationError, CameraUnreachableError, DomainError
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution

logger = structlog.get_logger(__name__)

# ONVIF's base `tt:VideoEncoding` enum (onvif.xsd) only defines JPEG/MPEG4/H264;
# H.265 support is a later, vendor-inconsistent extension, so it's mapped
# defensively rather than assumed absent.
_ONVIF_ENCODING_TO_CODEC = {
    "JPEG": Codec.MJPEG,
    "MPEG4": Codec.MPEG4,
    "H264": Codec.H264,
    "H265": Codec.H265,
}

# Best-effort classification of a raw ONVIF/zeep failure into "wrong
# credentials" vs. "camera unreachable for some other reason" — see
# docs/TECHNICAL_DECISIONS.md TD-18 for why this is a heuristic, not a
# guarantee: different camera vendors phrase WS-Security auth faults
# differently, and the onvif-zeep-async library itself does not distinguish
# them for anything but its HTTP-snapshot (401) path.
_AUTH_FAULT_HINTS = (
    "notauthorized",
    "failedauthentication",
    "unauthorized",
    "authentication",
    "invalid username or password",
    "password mismatch",  # confirmed vendor wording: Matrix MIDR20FL28CWS
    "permission",
    "access denied",
    "forbidden",
)


def classify_onvif_error(exc: Exception) -> DomainError:
    """Translate a raw ONVIF/zeep/transport exception into a typed domain exception."""
    message = str(exc).lower()
    auth_error_type = type(exc).__name__ == "ONVIFAuthError"
    if auth_error_type or any(hint in message for hint in _AUTH_FAULT_HINTS):
        return CameraAuthenticationError(str(exc) or "Camera rejected the supplied credentials")
    return CameraUnreachableError(str(exc) or "Camera could not be reached")


def map_codec(encoding: str) -> Codec | None:
    """Map an ONVIF `VideoEncoding` string to the domain `Codec`.

    Returns None (rather than raising) for an encoding this system doesn't
    recognize, so a single unusual profile doesn't fail the entire onboarding.
    """
    codec = _ONVIF_ENCODING_TO_CODEC.get(str(encoding).upper())
    if codec is None:
        logger.warning("onvif.unknown_codec", encoding=encoding)
    return codec


def map_device_info(ip_address: str, username: str, info: Any) -> Camera:
    """Map a `GetDeviceInformation` response into a partially-populated `Camera`.

    Per `ICameraGateway.get_device_info`'s contract, only manufacturer/model/
    firmware are meaningful here — name/ip_address/username are placeholders
    the use case discards in favor of the real onboarding data.
    """
    return Camera(
        name=ip_address,
        ip_address=ip_address,
        username=username,
        manufacturer=getattr(info, "Manufacturer", None),
        model=getattr(info, "Model", None),
        firmware_version=getattr(info, "FirmwareVersion", None),
    )


def map_profile(profile: Any) -> StreamProfile | None:
    """Map one ONVIF `Profile` into a `StreamProfile`, or None if it can't be.

    Per the ONVIF schema, `VideoEncoderConfiguration` and its `RateControl`
    are both optional (e.g. audio-only profiles, or a camera that omits rate
    control). `StreamProfile` requires resolution/codec/bitrate/fps with no
    defaults, so a profile missing either is skipped rather than persisted
    with fabricated placeholder values.
    """
    name = getattr(profile, "Name", None)
    token = getattr(profile, "token", None)
    enc_config = getattr(profile, "VideoEncoderConfiguration", None)
    if name is None or enc_config is None:
        logger.warning("onvif.profile_missing_encoder_config", token=token)
        return None

    rate_control = getattr(enc_config, "RateControl", None)
    if rate_control is None:
        logger.warning("onvif.profile_missing_rate_control", token=token, name=name)
        return None

    codec = map_codec(getattr(enc_config, "Encoding", ""))
    if codec is None:
        return None

    resolution = getattr(enc_config, "Resolution", None)
    if resolution is None:
        logger.warning("onvif.profile_missing_resolution", token=token, name=name)
        return None

    return StreamProfile(
        name=str(name),
        resolution=Resolution(width=resolution.Width, height=resolution.Height),
        codec=codec,
        bitrate=BitrateKbps(value=rate_control.BitrateLimit),
        fps=rate_control.FrameRateLimit,
        onvif_token=str(token) if token is not None else None,
    )
