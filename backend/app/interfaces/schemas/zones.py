from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.analytics_zone import AnalyticsZone


class ZoneCreateRequest(BaseModel):
    """POST /zones body (T-111)."""

    camera_id: UUID
    name: str = Field(min_length=1)
    polygon: list[tuple[float, float]] = Field(min_length=3)
    dwell_threshold_seconds: float = Field(gt=0)
    # Opt-in per zone (M12/T-120): omitted/null means MissingObjectDetector
    # skips this zone entirely, unlike dwell_threshold_seconds which every
    # zone always has.
    missing_object_threshold_seconds: float | None = Field(default=None, gt=0)


class ZoneUpdateRequest(BaseModel):
    """PATCH /zones/{id} body. Every field is optional — an omitted field is
    left at its current persisted value."""

    name: str | None = Field(default=None, min_length=1)
    polygon: list[tuple[float, float]] | None = Field(default=None, min_length=3)
    dwell_threshold_seconds: float | None = Field(default=None, gt=0)
    missing_object_threshold_seconds: float | None = Field(default=None, gt=0)


class ZoneResponse(BaseModel):
    id: UUID
    camera_id: UUID
    name: str
    polygon: list[tuple[float, float]]
    dwell_threshold_seconds: float
    missing_object_threshold_seconds: float | None = None

    @classmethod
    def from_domain(cls, zone: AnalyticsZone) -> "ZoneResponse":
        return cls(
            id=zone.id,
            camera_id=zone.camera_id,
            name=zone.name,
            polygon=zone.polygon,
            dwell_threshold_seconds=zone.dwell_threshold_seconds,
            missing_object_threshold_seconds=zone.missing_object_threshold_seconds,
        )
