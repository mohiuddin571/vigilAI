from dataclasses import dataclass

from app.domain.entities.stream_profile import StreamProfile
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities


@dataclass(frozen=True)
class CameraConfigUpdate:
    """A partial `PATCH /cameras/{id}/config` request — only the fields being changed.

    `None` means "leave this field at its current live value" — see
    `UpdateCameraConfigUseCase`, which merges this onto a fresh live read
    before applying it (ONVIF's `SetVideoEncoderConfiguration` requires the
    full configuration, not a delta).
    """

    resolution: Resolution | None = None
    codec: Codec | None = None
    bitrate: BitrateKbps | None = None
    fps: int | None = None


@dataclass(frozen=True)
class CameraConfigDTO:
    """The result of `GetCameraConfigUseCase`: current live values plus the
    camera-reported range of values it will accept for a PATCH.
    """

    profile: StreamProfile
    capabilities: VideoEncoderCapabilities
