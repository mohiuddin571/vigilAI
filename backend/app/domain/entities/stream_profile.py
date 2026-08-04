from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.exceptions import InvalidDomainStateError
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution


@dataclass
class StreamProfile:
    """A named bundle of video source + encoder configuration a camera exposes."""

    name: str
    resolution: Resolution
    codec: Codec
    bitrate: BitrateKbps
    fps: int
    id: UUID = field(default_factory=uuid4)
    is_primary: bool = False
    onvif_token: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidDomainStateError("StreamProfile name must not be empty")
        if self.fps <= 0:
            raise InvalidDomainStateError(f"fps must be positive, got {self.fps}")
