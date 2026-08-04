from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from app.domain.exceptions import InvalidDomainStateError


@dataclass(eq=False)
class Frame:
    """A single decoded frame yielded by an `IFrameSource`.

    The one abstraction every detector plugin and live-view consumer depends
    on instead of ONVIF/RTSP/MP4 specifics (see docs/ARCHITECTURE.md §5).

    `sequence` is scoped to one `start()`/`stop()` session of the source it
    came from, not a global counter — it resets to 0 each time a source is
    (re)started, including on reconnect.

    Equality is identity-based (`eq=False`): comparing two frames' pixel
    arrays for equality has no meaningful domain semantics, and the default
    dataclass `__eq__` would try `image == other.image`, which raises on
    numpy arrays (ambiguous truth value) rather than doing anything useful.
    """

    source_id: str
    sequence: int
    timestamp: datetime
    image: np.ndarray = field(repr=False)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise InvalidDomainStateError("Frame source_id must not be empty")
        if self.sequence < 0:
            raise InvalidDomainStateError(f"Frame sequence must be >= 0, got {self.sequence}")
        if self.image.ndim not in (2, 3):
            raise InvalidDomainStateError(
                f"Frame image must be a 2D or 3D array, got ndim={self.image.ndim}"
            )
