from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class StreamState(StrEnum):
    """Lifecycle state of a supervised `IStreamWorker`.

    Distinct from `IFrameSource` itself knowing nothing about "reconnecting"
    — that's the Stream Worker's supervision concern, not the source's (see
    docs/ARCHITECTURE.md §6.2).
    """

    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    STOPPED = "stopped"


class StreamHealth(BaseModel):
    """A point-in-time health snapshot reported by `IStreamWorker.health()`."""

    model_config = ConfigDict(frozen=True)

    state: StreamState
    last_frame_at: datetime | None = None
    consecutive_failures: int = 0
    last_error: str | None = None
