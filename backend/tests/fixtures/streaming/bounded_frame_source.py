"""A plain, cleanly-terminating fake `IFrameSource` — yields a fixed number of frames then stops.

Distinct from `FlakyFrameSource` (which simulates disconnects by raising):
this one is for tests that need a *source-independence* comparison against a
real `IFrameSource` implementation, where the desired behavior on both sides
is "produce N frames, then end `frames()` cleanly" — not reconnect/backoff
behavior (that's `ReconnectSupervisor`'s own T-024 test's job).
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import numpy as np

from app.application.ports.frame_source import IFrameSource
from app.domain.entities.frame import Frame


class BoundedFrameSource(IFrameSource):
    def __init__(self, source_id: str = "bounded-fake", *, frame_count: int = 5) -> None:
        self._source_id = source_id
        self._frame_count = frame_count
        self.start_calls = 0
        self.stop_calls = 0

    @property
    def source_id(self) -> str:
        return self._source_id

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def frames(self) -> AsyncIterator[Frame]:
        for sequence in range(self._frame_count):
            yield Frame(
                source_id=self._source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.zeros((2, 2, 3), dtype=np.uint8),
            )
