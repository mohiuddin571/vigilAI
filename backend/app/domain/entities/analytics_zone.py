from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.exceptions import InvalidDomainStateError


@dataclass
class AnalyticsZone:
    """A named polygon region on a camera's frame, used by zone-aware detectors.

    `polygon` points and `LoiteringDetector`'s bounding-box containment checks
    both live in the same normalized `[0, 1]` space `BoundingBox` already uses
    (M11/T-111) — the frontend zone editor normalizes drawn pixel points on
    save, so no coordinate conversion is needed at containment-check time
    (docs/TECHNICAL_DECISIONS.md TD-28).

    `missing_object_threshold_seconds` (M12/T-120, docs/TECHNICAL_DECISIONS.md
    TD-29) is additive and optional, unlike `dwell_threshold_seconds`: a zone
    always participates in loitering detection, but missing-object monitoring
    is opt-in per zone — `None` (the default) means `MissingObjectDetector`
    skips this zone entirely.
    """

    camera_id: UUID
    name: str
    polygon: list[tuple[float, float]]
    dwell_threshold_seconds: float
    missing_object_threshold_seconds: float | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidDomainStateError("AnalyticsZone name must not be empty")
        if len(self.polygon) < 3:
            raise InvalidDomainStateError(
                f"AnalyticsZone polygon needs at least 3 points, got {len(self.polygon)}"
            )
        if self.dwell_threshold_seconds <= 0:
            raise InvalidDomainStateError(
                "AnalyticsZone dwell_threshold_seconds must be > 0, got "
                f"{self.dwell_threshold_seconds}"
            )
        if (
            self.missing_object_threshold_seconds is not None
            and self.missing_object_threshold_seconds <= 0
        ):
            raise InvalidDomainStateError(
                "AnalyticsZone missing_object_threshold_seconds must be > 0 if set, got "
                f"{self.missing_object_threshold_seconds}"
            )
