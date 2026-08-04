from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.exceptions import InvalidDomainStateError


@dataclass
class AnalyticsZone:
    """A named polygon region on a camera's frame, used by zone-aware detectors."""

    camera_id: UUID
    name: str
    polygon: list[tuple[float, float]]
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidDomainStateError("AnalyticsZone name must not be empty")
        if len(self.polygon) < 3:
            raise InvalidDomainStateError(
                f"AnalyticsZone polygon needs at least 3 points, got {len(self.polygon)}"
            )
