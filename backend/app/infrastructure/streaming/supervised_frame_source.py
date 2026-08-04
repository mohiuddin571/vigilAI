from collections.abc import AsyncIterator, Sequence

from app.application.ports.frame_source import IFrameSource
from app.domain.entities.frame import Frame
from app.infrastructure.streaming.reconnect_supervisor import ReconnectSupervisor


class SupervisedFrameSource(IFrameSource):
    """Wraps any `IFrameSource` with `ReconnectSupervisor`'s reconnect/backoff loop.

    `ReconnectSupervisor` (M2, docs/TECHNICAL_DECISIONS.md TD-20) was
    deliberately split out from `StreamWorker`'s process isolation so it can
    be reused directly, in-process, by anything that wants the same
    reconnect/backoff policy without needing a full `multiprocessing`
    Stream Worker. This adapter re-exposes that reuse as an `IFrameSource`
    itself, so callers depending on the `IFrameSource` port (like
    `RunAnalyticsPipelineUseCase`) get supervised consumption — "the same
    supervised path" M5's live-view/M6's recording already build on,
    without duplicating or bypassing `ReconnectSupervisor`'s logic
    (docs/IMPLEMENTATION_PLAN.md §M8's Constraints).

    No process isolation here — that remains `StreamWorker`'s job when an
    acceptance criterion actually requires it (T-023); nothing in M8 does.
    """

    def __init__(self, source: IFrameSource, backoff_schedule: Sequence[float]) -> None:
        self._supervisor = ReconnectSupervisor(source, backoff_schedule)
        self._source_id = source.source_id
        self._frames_iter: AsyncIterator[Frame] | None = None

    @property
    def source_id(self) -> str:
        return self._source_id

    async def start(self) -> None:
        self._frames_iter = self._supervisor.run()

    async def stop(self) -> None:
        self._supervisor.stop()

    async def frames(self) -> AsyncIterator[Frame]:
        assert self._frames_iter is not None, "start() must succeed before frames() is iterated"
        async for frame in self._frames_iter:
            yield frame
