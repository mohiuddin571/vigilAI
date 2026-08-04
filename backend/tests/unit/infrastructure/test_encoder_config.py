from types import SimpleNamespace

import pytest

from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraNotFoundError, UnsupportedConfigurationError
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities
from app.infrastructure.onvif.encoder_config import (
    apply_stream_profile_to_raw_configuration,
    map_video_encoder_configuration,
    map_video_encoder_configuration_options,
    resolve_video_encoder_configuration_token,
    validate_requested_configuration,
)


def _raw_config(
    *,
    encoding: str = "H264",
    width: int = 1920,
    height: int = 1080,
    bitrate: int = 4096,
    fps: int = 25,
    name: str | None = "VideoEncoder_1",
    token: str | None = "VideoEncoderToken_1",
    has_rate_control: bool = True,
    has_resolution: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        Name=name,
        token=token,
        Encoding=encoding,
        Resolution=SimpleNamespace(Width=width, Height=height) if has_resolution else None,
        RateControl=(
            SimpleNamespace(FrameRateLimit=fps, EncodingInterval=1, BitrateLimit=bitrate)
            if has_rate_control
            else None
        ),
    )


def _raw_options(
    *,
    codec_field: str = "H264",
    resolutions: list[tuple[int, int]] | None = None,
    fps_range: tuple[int, int] = (1, 30),
    bitrate_range: tuple[int, int] | None = (512, 8192),
) -> SimpleNamespace:
    resolutions = resolutions or [(1920, 1080), (1280, 720)]
    codec_options = SimpleNamespace(
        ResolutionsAvailable=[SimpleNamespace(Width=w, Height=h) for w, h in resolutions],
        FrameRateRange=SimpleNamespace(Min=fps_range[0], Max=fps_range[1]),
    )
    extension = None
    if bitrate_range is not None:
        extension = SimpleNamespace(
            **{
                codec_field: SimpleNamespace(
                    BitrateRange=SimpleNamespace(Min=bitrate_range[0], Max=bitrate_range[1])
                )
            }
        )
    return SimpleNamespace(**{codec_field: codec_options, "Extension": extension})


def _profile_ns(
    *, token: str = "Profile_1", config_token: str | None = "VideoEncoderToken_1"
) -> SimpleNamespace:
    enc_config = SimpleNamespace(token=config_token) if config_token is not None else None
    return SimpleNamespace(token=token, VideoEncoderConfiguration=enc_config)


class _FakeMedia:
    def __init__(self, profiles: list[SimpleNamespace]) -> None:
        self._profiles = profiles

    async def GetProfiles(self) -> list[SimpleNamespace]:
        return self._profiles


# --- resolve_video_encoder_configuration_token ---


async def test_resolve_token_finds_matching_profile() -> None:
    media = _FakeMedia([_profile_ns(token="Profile_1", config_token="VideoEncoderToken_1")])
    token = await resolve_video_encoder_configuration_token(media, "Profile_1")
    assert token == "VideoEncoderToken_1"


async def test_resolve_token_raises_not_found_for_unknown_profile() -> None:
    media = _FakeMedia([_profile_ns(token="Profile_1")])
    with pytest.raises(CameraNotFoundError):
        await resolve_video_encoder_configuration_token(media, "Profile_99")


async def test_resolve_token_raises_unsupported_when_profile_has_no_encoder_config() -> None:
    media = _FakeMedia([_profile_ns(token="Profile_1", config_token=None)])
    with pytest.raises(UnsupportedConfigurationError):
        await resolve_video_encoder_configuration_token(media, "Profile_1")


# --- map_video_encoder_configuration ---


def test_map_video_encoder_configuration_success() -> None:
    profile = map_video_encoder_configuration(_raw_config())
    assert profile is not None
    assert profile.resolution == Resolution(width=1920, height=1080)
    assert profile.codec == Codec.H264
    assert profile.bitrate == BitrateKbps(value=4096)
    assert profile.fps == 25
    assert profile.onvif_token == "VideoEncoderToken_1"


def test_map_video_encoder_configuration_unknown_codec_returns_none() -> None:
    assert map_video_encoder_configuration(_raw_config(encoding="VP9")) is None


def test_map_video_encoder_configuration_missing_rate_control_returns_none() -> None:
    assert map_video_encoder_configuration(_raw_config(has_rate_control=False)) is None


def test_map_video_encoder_configuration_missing_resolution_returns_none() -> None:
    assert map_video_encoder_configuration(_raw_config(has_resolution=False)) is None


# --- map_video_encoder_configuration_options ---


def test_map_options_success_with_bitrate_extension() -> None:
    capabilities = map_video_encoder_configuration_options(_raw_options(), Codec.H264)
    assert capabilities.codec == Codec.H264
    assert Resolution(width=1920, height=1080) in capabilities.resolutions
    assert capabilities.fps_min == 1
    assert capabilities.fps_max == 30
    assert capabilities.bitrate_min_kbps == 512
    assert capabilities.bitrate_max_kbps == 8192


def test_map_options_without_bitrate_extension_leaves_bitrate_bounds_none() -> None:
    capabilities = map_video_encoder_configuration_options(
        _raw_options(codec_field="JPEG", bitrate_range=None), Codec.MJPEG
    )
    assert capabilities.bitrate_min_kbps is None
    assert capabilities.bitrate_max_kbps is None


def test_map_options_raises_when_codec_section_missing() -> None:
    raw_options = _raw_options(codec_field="JPEG")
    with pytest.raises(UnsupportedConfigurationError):
        map_video_encoder_configuration_options(raw_options, Codec.H264)


def test_map_options_raises_for_unmodeled_codec() -> None:
    raw_options = _raw_options()
    with pytest.raises(UnsupportedConfigurationError):
        map_video_encoder_configuration_options(raw_options, Codec.H265)


# --- validate_requested_configuration ---


def _capabilities(**overrides: object) -> VideoEncoderCapabilities:
    defaults: dict[str, object] = {
        "codec": Codec.H264,
        "resolutions": [Resolution(width=1920, height=1080), Resolution(width=1280, height=720)],
        "fps_min": 1,
        "fps_max": 30,
        "bitrate_min_kbps": 512,
        "bitrate_max_kbps": 8192,
    }
    defaults.update(overrides)
    return VideoEncoderCapabilities(**defaults)  # type: ignore[arg-type]


def _requested(**overrides: object) -> StreamProfile:
    defaults: dict[str, object] = {
        "name": "MainStream",
        "resolution": Resolution(width=1920, height=1080),
        "codec": Codec.H264,
        "bitrate": BitrateKbps(value=4096),
        "fps": 25,
    }
    defaults.update(overrides)
    return StreamProfile(**defaults)  # type: ignore[arg-type]


def test_validate_accepts_supported_configuration() -> None:
    validate_requested_configuration(_requested(), _capabilities())


def test_validate_rejects_codec_change() -> None:
    with pytest.raises(UnsupportedConfigurationError):
        validate_requested_configuration(_requested(codec=Codec.MJPEG), _capabilities())


def test_validate_rejects_unsupported_resolution() -> None:
    with pytest.raises(UnsupportedConfigurationError):
        validate_requested_configuration(
            _requested(resolution=Resolution(width=640, height=480)), _capabilities()
        )


def test_validate_rejects_fps_out_of_range() -> None:
    with pytest.raises(UnsupportedConfigurationError):
        validate_requested_configuration(_requested(fps=60), _capabilities())


def test_validate_rejects_bitrate_out_of_range() -> None:
    with pytest.raises(UnsupportedConfigurationError):
        validate_requested_configuration(
            _requested(bitrate=BitrateKbps(value=99_999)), _capabilities()
        )


def test_validate_skips_bitrate_check_when_capability_unreported() -> None:
    validate_requested_configuration(
        _requested(bitrate=BitrateKbps(value=99_999)),
        _capabilities(bitrate_min_kbps=None, bitrate_max_kbps=None),
    )


# --- apply_stream_profile_to_raw_configuration ---


def test_apply_stream_profile_mutates_only_expected_fields() -> None:
    raw_config = _raw_config()
    profile = _requested(
        resolution=Resolution(width=1280, height=720),
        bitrate=BitrateKbps(value=2048),
        fps=15,
    )

    apply_stream_profile_to_raw_configuration(raw_config, profile)

    assert raw_config.Resolution.Width == 1280
    assert raw_config.Resolution.Height == 720
    assert raw_config.RateControl.BitrateLimit == 2048
    assert raw_config.RateControl.FrameRateLimit == 15
    # Untouched fields survive.
    assert raw_config.Encoding == "H264"
    assert raw_config.token == "VideoEncoderToken_1"
