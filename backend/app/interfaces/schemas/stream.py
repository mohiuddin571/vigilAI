from datetime import datetime

from pydantic import BaseModel

from app.domain.value_objects.stream_health import StreamHealth


class StreamStatusResponse(BaseModel):
    """Response/WS-message shape for a camera's live-stream health (T-052/T-053)."""

    state: str
    last_frame_at: datetime | None
    consecutive_failures: int
    last_error: str | None

    @classmethod
    def from_health(cls, health: StreamHealth) -> "StreamStatusResponse":
        return cls(
            state=health.state.value,
            last_frame_at=health.last_frame_at,
            consecutive_failures=health.consecutive_failures,
            last_error=health.last_error,
        )
