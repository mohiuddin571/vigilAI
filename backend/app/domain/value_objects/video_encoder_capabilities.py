from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution


class VideoEncoderCapabilities(BaseModel):
    """The camera-reported range of legal values for one profile's encoder config.

    Sourced from ONVIF's `GetVideoEncoderConfigurationOptions` (see
    `infrastructure/onvif/encoder_config.py`). `codec` is the profile's current,
    fixed encoding — codec switching is not modeled as a capability here (see
    docs/TECHNICAL_DECISIONS.md TD-19).
    """

    model_config = ConfigDict(frozen=True)

    codec: Codec
    resolutions: list[Resolution] = Field(min_length=1)
    fps_min: int = Field(gt=0)
    fps_max: int = Field(gt=0)
    bitrate_min_kbps: int | None = Field(default=None, gt=0)
    bitrate_max_kbps: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_ranges(self) -> "VideoEncoderCapabilities":
        if self.fps_min > self.fps_max:
            raise ValueError(f"fps_min ({self.fps_min}) must be <= fps_max ({self.fps_max})")
        if (self.bitrate_min_kbps is None) != (self.bitrate_max_kbps is None):
            raise ValueError("bitrate_min_kbps and bitrate_max_kbps must be provided together")
        if (
            self.bitrate_min_kbps is not None
            and self.bitrate_max_kbps is not None
            and self.bitrate_min_kbps > self.bitrate_max_kbps
        ):
            raise ValueError(
                f"bitrate_min_kbps ({self.bitrate_min_kbps}) must be <= "
                f"bitrate_max_kbps ({self.bitrate_max_kbps})"
            )
        return self
