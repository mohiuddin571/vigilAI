"""A fake flaky `IFrameSource` — T-024's required reconnect/backoff test double.

Fails `start()` a configurable number of times before succeeding, and can
also be made to drop mid-stream after a configurable number of frames, so
`ReconnectSupervisor` can be exercised against both "can't open" and
"opened, then died" disconnect shapes with no real I/O.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import numpy as np

from app.application.ports.frame_source import IFrameSource
from app.domain.entities.frame import Frame
from app.domain.exceptions import FrameSourceUnavailableError


class FlakyFrameSource(IFrameSource):
    def __init__(
        self,
        source_id: str = "flaky",
        *,
        fail_start_times: int = 0,
        fail_after_frames: int | None = None,
    ) -> None:
        self._source_id = source_id
        self._fail_start_times = fail_start_times
        self._fail_after_frames = fail_after_frames
        self.start_attempts = 0
        self._started = False

    @property
    def source_id(self) -> str:
        return self._source_id

    async def start(self) -> None:
        self.start_attempts += 1
        if self.start_attempts <= self._fail_start_times:
            raise FrameSourceUnavailableError(f"simulated open failure #{self.start_attempts}")
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def frames(self) -> AsyncIterator[Frame]:
        if not self._started:
            raise FrameSourceUnavailableError("start() must succeed before frames() is iterated")
        sequence = 0
        while True:
            if self._fail_after_frames is not None and sequence >= self._fail_after_frames:
                raise FrameSourceUnavailableError("simulated mid-stream disconnect")
            yield Frame(
                source_id=self._source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.zeros((2, 2, 3), dtype=np.uint8),
            )
            sequence += 1
