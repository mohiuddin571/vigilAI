import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import datetime

import structlog

from app.application.ports.frame_source import IFrameSource
from app.domain.entities.frame import Frame
from app.domain.exceptions import FrameSourceUnavailableError
from app.domain.value_objects.stream_health import StreamHealth, StreamState

logger = structlog.get_logger(__name__)


class ReconnectSupervisor:
    """Wraps any `IFrameSource` with the source-agnostic reconnect/backoff policy (T-024).

    The same policy applies whether the source "reconnects" by re-opening a
    file (MP4) or re-establishing a network connection (camera, added in
    M5) — docs/ARCHITECTURE.md §6.2. Deliberately has no knowledge of
    process isolation (that's `StreamWorker`'s job, T-023) so this loop is
    unit-testable in-process against a fake flaky `IFrameSource`, with no
    real I/O — this is the test T-024 requires and that must never be
    weakened, mirroring T-086's permanence for the analytics pipeline.

    Retries indefinitely with a capped backoff — there is no "give up after
    N attempts" policy in this milestone, so `StreamState.FAILED` is never
    emitted by this class (it's reserved for a future bounded-retry policy,
    not yet required by any acceptance criterion).
    """

    def __init__(
        self,
        source: IFrameSource,
        backoff_schedule: Sequence[float],
        *,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if not backoff_schedule:
            raise ValueError("backoff_schedule must not be empty")
        self._source = source
        self._backoff_schedule = backoff_schedule
        self._sleep = sleep or _default_sleep
        self._state = StreamState.CONNECTING
        self._ever_connected = False
        self._last_frame_at: datetime | None = None
        self._consecutive_failures = 0
        self._last_error: str | None = None
        self._stopped = False

    def health(self) -> StreamHealth:
        return StreamHealth(
            state=self._state,
            last_frame_at=self._last_frame_at,
            consecutive_failures=self._consecutive_failures,
            last_error=self._last_error,
        )

    def stop(self) -> None:
        """Request the supervised loop stop at its next opportunity."""
        self._stopped = True

    async def run(self) -> AsyncIterator[Frame]:
        """Runs the supervised open→consume→backoff→retry loop until `stop()`."""
        while not self._stopped:
            self._state = (
                StreamState.CONNECTING if not self._ever_connected else StreamState.RECONNECTING
            )
            try:
                await self._source.start()
            except Exception as exc:
                await self._handle_failure(exc)
                continue

            self._ever_connected = True
            self._consecutive_failures = 0
            self._last_error = None
            self._state = StreamState.CONNECTED
            try:
                async for frame in self._source.frames():
                    if self._stopped:
                        break
                    self._last_frame_at = frame.timestamp
                    yield frame
                else:
                    if not self._stopped:
                        await self._handle_failure(
                            FrameSourceUnavailableError("frame stream ended unexpectedly")
                        )
            except Exception as exc:
                if not self._stopped:
                    await self._handle_failure(exc)
            finally:
                await self._source.stop()

        self._state = StreamState.STOPPED

    async def _handle_failure(self, exc: Exception) -> None:
        self._last_error = str(exc)
        self._state = StreamState.RECONNECTING
        index = min(self._consecutive_failures, len(self._backoff_schedule) - 1)
        delay = self._backoff_schedule[index]
        self._consecutive_failures += 1
        logger.warning(
            "stream.reconnect_backoff",
            source_id=self._source.source_id,
            error=self._last_error,
            delay_seconds=delay,
            attempt=self._consecutive_failures,
        )
        await self._sleep(delay)


async def _default_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)
