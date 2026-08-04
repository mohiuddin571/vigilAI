from datetime import datetime

from pydantic import BaseModel

from app.application.dto.debug_stream import DebugStreamStatus


class LatestFrameMetadataResponse(BaseModel):
    source_id: str
    sequence: int
    timestamp: datetime
    image_shape: tuple[int, ...]


class DebugStreamStatusResponse(BaseModel):
    """GET /debug/streams/mp4 response — T-025's "latest frame metadata"."""

    state: str
    last_frame_at: datetime | None
    consecutive_failures: int
    last_error: str | None
    latest_frame: LatestFrameMetadataResponse | None

    @classmethod
    def from_dto(cls, dto: DebugStreamStatus) -> "DebugStreamStatusResponse":
        return cls(
            state=dto.health.state.value,
            last_frame_at=dto.health.last_frame_at,
            consecutive_failures=dto.health.consecutive_failures,
            last_error=dto.health.last_error,
            latest_frame=(
                LatestFrameMetadataResponse(
                    source_id=dto.latest_frame.source_id,
                    sequence=dto.latest_frame.sequence,
                    timestamp=dto.latest_frame.timestamp,
                    image_shape=dto.latest_frame.image_shape,
                )
                if dto.latest_frame is not None
                else None
            ),
        )
