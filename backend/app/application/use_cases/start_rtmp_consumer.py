import asyncio
import contextlib
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from app.application.ports.stream_worker import IStreamWorker
from app.domain.entities.frame import Frame
from app.domain.exceptions import FrameSourceUnavailableError
from app.domain.value_objects.stream_health import StreamHealth, StreamState

_FPS_WINDOW_SIZE = 30


@dataclass(frozen=True)
class RtmpConsumerDiagnostics:
    """Observed-at-runtime playback diagnostics for the RTMP Consumer (docs/RTMP_DEMO.md).

    Deliberately kept local to this use case rather than folded into the
    shared `StreamHealth`/`Frame` domain types — this is RTMP-demo-specific
    presentation data, not a concept the rest of the system needs.
    """

    resolution: tuple[int, int] | None  # (width, height), from the latest frame's shape
    observed_fps: float | None  # rolling average over the last _FPS_WINDOW_SIZE frames


class _RtmpStreamHandle:
    """A small, deliberate duplicate of `start_demo_stream.py`'s private `_StreamHandle`
    (same one-worker/many-viewers fan-out shape), extended to also track a rolling window of
    frame arrival timestamps for `RtmpConsumerDiagnostics` — kept as its own copy rather than
    generalizing the shared shape, per this repo's own small-duplication-over-cross-cutting-
    abstraction precedent (docs/TECHNICAL_DECISIONS.md TD-25/TD-29)."""

    def __init__(self, worker: IStreamWorker) -> None:
        self.worker = worker
        self._latest_frame: Frame | None = None
        self._frame_timestamps: deque[float] = deque(maxlen=_FPS_WINDOW_SIZE)
        self._condition = asyncio.Condition()
        self._stopped = False
        self.consume_task: asyncio.Task[None] | None = None

    async def start_consuming(self) -> None:
        self.consume_task = asyncio.create_task(self._consume())

    async def _consume(self) -> None:
        loop = asyncio.get_running_loop()
        async for frame in self.worker.frames():
            async with self._condition:
                self._latest_frame = frame
                self._frame_timestamps.append(loop.time())
                self._condition.notify_all()

    async def frames(self) -> AsyncIterator[Frame]:
        last_sequence: int | None = None
        while True:

            def _has_new_frame(seq: int | None = last_sequence) -> bool:
                return self._stopped or (
                    self._latest_frame is not None and self._latest_frame.sequence != seq
                )

            async with self._condition:
                await self._condition.wait_for(_has_new_frame)
                if self._stopped:
                    return
                frame = self._latest_frame
            assert frame is not None
            last_sequence = frame.sequence
            yield frame

    def health(self) -> StreamHealth:
        return self.worker.health()

    def diagnostics(self) -> RtmpConsumerDiagnostics:
        frame = self._latest_frame
        resolution = (frame.image.shape[1], frame.image.shape[0]) if frame is not None else None
        observed_fps = None
        timestamps = list(self._frame_timestamps)
        if len(timestamps) >= 2:
            elapsed = timestamps[-1] - timestamps[0]
            if elapsed > 0:
                observed_fps = (len(timestamps) - 1) / elapsed
        return RtmpConsumerDiagnostics(resolution=resolution, observed_fps=observed_fps)

    async def stop(self) -> None:
        if self.consume_task is not None:
            self.consume_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.consume_task
            self.consume_task = None
        await self.worker.stop()
        async with self._condition:
            self._stopped = True
            self._frame_timestamps.clear()
            self._condition.notify_all()


class StartRtmpConsumerUseCase:
    """Start/stop/observe the RTMP demo consumer — connects to the RTMP demo server and decodes
    the published stream (docs/RTMP_DEMO.md).

    A deliberate small duplicate of `StartDemoStreamUseCase`, simplified
    further: there is exactly one fixed RTMP endpoint for this demo (no
    caller-supplied id), so this holds at most one `_RtmpStreamHandle` rather
    than a dict keyed by id.
    """

    def __init__(self, build_stream_worker: Callable[[], IStreamWorker]) -> None:
        self._build_stream_worker = build_stream_worker
        self._handle: _RtmpStreamHandle | None = None
        self._lock = asyncio.Lock()

    async def execute(self) -> None:
        async with self._lock:
            if self._handle is not None:
                return
            worker = self._build_stream_worker()
            await worker.start()
            handle = _RtmpStreamHandle(worker)
            await handle.start_consuming()
            self._handle = handle

    async def stop(self) -> None:
        async with self._lock:
            handle = self._handle
            self._handle = None
            if handle is not None:
                await handle.stop()

    async def stop_all(self) -> None:
        """Mirrors `StartDemoStreamUseCase.stop_all`'s graceful-shutdown role — called from the
        composition root's shutdown path so no consumer `StreamWorker` process is left orphaned."""
        await self.stop()

    def frames(self) -> AsyncIterator[Frame]:
        handle = self._handle
        if handle is None:
            raise FrameSourceUnavailableError("No RTMP consumer is running")
        return handle.frames()

    def health(self) -> StreamHealth:
        handle = self._handle
        if handle is None:
            return StreamHealth(state=StreamState.STOPPED)
        return handle.health()

    def diagnostics(self) -> RtmpConsumerDiagnostics:
        handle = self._handle
        if handle is None:
            return RtmpConsumerDiagnostics(resolution=None, observed_fps=None)
        return handle.diagnostics()
