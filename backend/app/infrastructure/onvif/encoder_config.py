"""ONVIF video-encoder configuration read/update and capability mapping (M4, T-040/T-041).

Used by `OnvifCameraGateway`. `profile_id` throughout is the *profile's* own
ONVIF token (`StreamProfile.onvif_token`, established at M3) — not the video
encoder configuration's own token. ONVIF addresses `GetVideoEncoderConfiguration`
/`SetVideoEncoderConfiguration`/`GetVideoEncoderConfigurationOptions` by the
encoder configuration's own `ConfigurationToken`, which is nested inside the
profile's `VideoEncoderConfiguration.token` — `resolve_video_encoder_configuration_token`
performs that lookup via `GetProfiles`.
"""

from typing import Any

import structlog

from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraNotFoundError, UnsupportedConfigurationError
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities
from app.infrastructure.onvif.mappers import map_codec

logger = structlog.get_logger(__name__)

# ONVIF's VideoEncoderConfigurationOptions groups ranges by codec-specific
# sub-element; H.265 has no base-schema options section (vendor extension
# territory), so it's deliberately absent here rather than guessed.
_CODEC_TO_OPTIONS_FIELD = {
    Codec.H264: "H264",
    Codec.MJPEG: "JPEG",
    Codec.MPEG4: "MPEG4",
}


async def resolve_video_encoder_configuration_token(media: Any, profile_id: str) -> str:
    """Find the video-encoder-configuration token addressed by a profile's own token.

    Raises:
        CameraNotFoundError: no profile with this token is currently reported
            by the camera.
        UnsupportedConfigurationError: that profile has no video encoder
            configuration at all (e.g. an audio-only profile).
    """
    profiles = await media.GetProfiles()
    for profile in profiles:
        if str(getattr(profile, "token", None)) != profile_id:
            continue
        enc_config = getattr(profile, "VideoEncoderConfiguration", None)
        token = getattr(enc_config, "token", None) if enc_config is not None else None
        if token is None:
            raise UnsupportedConfigurationError(
                f"Profile {profile_id!r} has no video encoder configuration"
            )
        return str(token)
    raise CameraNotFoundError(f"Camera does not currently report a profile {profile_id!r}")


def map_video_encoder_configuration(raw_config: Any) -> StreamProfile | None:
    """Map a raw `GetVideoEncoderConfiguration` response into a `StreamProfile`.

    Returns None if the reported encoding isn't one this system recognizes
    (see docs/TECHNICAL_DECISIONS.md TD-18) rather than guessing a codec.
    """
    codec = map_codec(getattr(raw_config, "Encoding", ""))
    if codec is None:
        return None
    rate_control = getattr(raw_config, "RateControl", None)
    if rate_control is None:
        logger.warning("onvif.encoder_config_missing_rate_control")
        return None
    resolution = getattr(raw_config, "Resolution", None)
    if resolution is None:
        logger.warning("onvif.encoder_config_missing_resolution")
        return None

    name = getattr(raw_config, "Name", None)
    token = getattr(raw_config, "token", None)
    return StreamProfile(
        name=str(name) if name is not None else "encoder-config",
        resolution=Resolution(width=resolution.Width, height=resolution.Height),
        codec=codec,
        bitrate=BitrateKbps(value=rate_control.BitrateLimit),
        fps=rate_control.FrameRateLimit,
        onvif_token=str(token) if token is not None else None,
    )


def map_video_encoder_configuration_options(
    raw_options: Any, codec: Codec
) -> VideoEncoderCapabilities:
    """Map a raw `GetVideoEncoderConfigurationOptions` response for one codec.

    Raises UnsupportedConfigurationError if the camera didn't report an
    options block for `codec` at all.
    """
    field_name = _CODEC_TO_OPTIONS_FIELD.get(codec)
    codec_options = getattr(raw_options, field_name, None) if field_name else None
    if codec_options is None:
        raise UnsupportedConfigurationError(
            f"Camera did not report {codec} encoder configuration options for this profile"
        )

    resolutions = [
        Resolution(width=r.Width, height=r.Height) for r in codec_options.ResolutionsAvailable
    ]
    fps_range = codec_options.FrameRateRange
    bitrate_range = _extract_bitrate_range(raw_options, codec)

    return VideoEncoderCapabilities(
        codec=codec,
        resolutions=resolutions,
        fps_min=fps_range.Min,
        fps_max=fps_range.Max,
        bitrate_min_kbps=bitrate_range.Min if bitrate_range is not None else None,
        bitrate_max_kbps=bitrate_range.Max if bitrate_range is not None else None,
    )


def _extract_bitrate_range(raw_options: Any, codec: Codec) -> Any | None:
    """`BitrateRange` only exists in ONVIF's v1.2 `Extension` block, per-codec.

    A camera that doesn't report it isn't necessarily unbounded — it just
    means this system has no reported bound to pre-validate against, so
    bitrate checks defer to the camera's own `SetVideoEncoderConfiguration`
    response in that case (see `OnvifCameraGateway.set_video_encoder_configuration`).
    """
    extension = getattr(raw_options, "Extension", None)
    if extension is None:
        return None
    field_name = _CODEC_TO_OPTIONS_FIELD.get(codec)
    ext_codec_options = getattr(extension, field_name, None) if field_name else None
    if ext_codec_options is None:
        return None
    return getattr(ext_codec_options, "BitrateRange", None)


def validate_requested_configuration(
    requested: StreamProfile, capabilities: VideoEncoderCapabilities
) -> None:
    """Raise UnsupportedConfigurationError for any field the camera doesn't support.

    Never silently ignores an unsupported field/value (T-041 DoD). Codec is
    treated as fixed per profile (see docs/TECHNICAL_DECISIONS.md TD-19) —
    ONVIF's options response doesn't assert whether a configuration can be
    switched to a different codec, so a codec change is always rejected here
    rather than guessed at.
    """
    if requested.codec != capabilities.codec:
        raise UnsupportedConfigurationError(
            f"Camera does not support changing codec from {capabilities.codec} "
            f"to {requested.codec} on this profile"
        )
    if requested.resolution not in capabilities.resolutions:
        supported = ", ".join(str(r) for r in capabilities.resolutions)
        raise UnsupportedConfigurationError(
            f"Camera does not support resolution {requested.resolution} for this "
            f"profile; supported: {supported}"
        )
    if not (capabilities.fps_min <= requested.fps <= capabilities.fps_max):
        raise UnsupportedConfigurationError(
            f"Camera does not support fps {requested.fps} for this profile; "
            f"supported range: {capabilities.fps_min}-{capabilities.fps_max}"
        )
    if capabilities.bitrate_min_kbps is not None and capabilities.bitrate_max_kbps is not None:
        bitrate = requested.bitrate.value
        if not (capabilities.bitrate_min_kbps <= bitrate <= capabilities.bitrate_max_kbps):
            raise UnsupportedConfigurationError(
                f"Camera does not support bitrate {bitrate}kbps for this profile; "
                f"supported range: {capabilities.bitrate_min_kbps}-"
                f"{capabilities.bitrate_max_kbps}kbps"
            )


def apply_stream_profile_to_raw_configuration(raw_config: Any, profile: StreamProfile) -> None:
    """Mutate only resolution/fps/bitrate on a raw config, in place.

    Deliberately leaves every other field (Encoding, Quality, Multicast,
    SessionTimeout, Name, UseCount, token, ...) untouched —
    `SetVideoEncoderConfiguration` requires the full object, and
    reconstructing unfamiliar mandatory fields from scratch risks silently
    corrupting camera-side settings this system doesn't model.
    """
    raw_config.Resolution.Width = profile.resolution.width
    raw_config.Resolution.Height = profile.resolution.height
    raw_config.RateControl.FrameRateLimit = profile.fps
    raw_config.RateControl.BitrateLimit = profile.bitrate.value
