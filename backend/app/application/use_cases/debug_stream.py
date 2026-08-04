import asyncio
import contextlib
from collections.abc import Callable

from app.application.dto.debug_stream import DebugStreamStatus, LatestFrameMetadata
from app.application.ports.stream_worker import IStreamWorker
from app.domain.value_objects.stream_health import StreamHealth, StreamState


class DebugStreamUseCase:
    """Start/stop/observe a single debug Stream Worker (docs/TASK_BACKLOG.md T-025).

    This exists purely to satisfy M2's own acceptance criterion that the
    Stream Worker's output be "observable via a debug endpoint" — it's
    dev/demo tooling for proving `IStreamWorker` works, not a persisted
    business operation, so unlike the other use cases it manages one
    in-memory worker rather than reading/writing a repository. Real
    camera live-view (MJPEG-over-HTTP, a resolved RTSP source) is M5's
    `StartLiveStreamUseCase` — out of scope here.
    """

    def __init__(self, build_worker: Callable[[], IStreamWorker]) -> None:
        self._build_worker = build_worker
        self._worker: IStreamWorker | None = None
        self._consume_task: asyncio.Task[None] | None = None
        self._latest_frame: LatestFrameMetadata | None = None

    async def start(self) -> None:
        if self._worker is not None:
            return
        worker = self._build_worker()
        await worker.start()
        self._worker = worker
        self._consume_task = asyncio.create_task(self._consume(worker))

    async def stop(self) -> None:
        if self._worker is None:
            return
        if self._consume_task is not None:
            self._consume_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consume_task
            self._consume_task = None
        await self._worker.stop()
        self._worker = None
        self._latest_frame = None

    def status(self) -> DebugStreamStatus:
        if self._worker is not None:
            health = self._worker.health()
        else:
            health = StreamHealth(state=StreamState.STOPPED)
        return DebugStreamStatus(health=health, latest_frame=self._latest_frame)

    async def _consume(self, worker: IStreamWorker) -> None:
        async for frame in worker.frames():
            self._latest_frame = LatestFrameMetadata(
                source_id=frame.source_id,
                sequence=frame.sequence,
                timestamp=frame.timestamp,
                image_shape=tuple(frame.image.shape),
            )
