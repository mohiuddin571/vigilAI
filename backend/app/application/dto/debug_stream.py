from dataclasses import dataclass
from datetime import datetime

from app.domain.value_objects.stream_health import StreamHealth


@dataclass(frozen=True)
class LatestFrameMetadata:
    """Lightweight metadata for the most recently observed frame — never the raw image array."""

    source_id: str
    sequence: int
    timestamp: datetime
    image_shape: tuple[int, ...]


@dataclass(frozen=True)
class DebugStreamStatus:
    """The result of `DebugStreamUseCase.status()` — T-025's "latest frame metadata"."""

    health: StreamHealth
    latest_frame: LatestFrameMetadata | None
