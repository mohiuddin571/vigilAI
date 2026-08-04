import asyncio
import contextlib
import queue
from collections.abc import AsyncIterator, Callable, Sequence
from multiprocessing import get_context
from multiprocessing.context import SpawnContext
from multiprocessing.process import BaseProcess
from multiprocessing.synchronize import Event as ProcessEvent
from typing import Any

import structlog

from app.application.ports.frame_source import IFrameSource
from app.application.ports.stream_worker import IStreamWorker
from app.domain.entities.frame import Frame
from app.domain.value_objects.stream_health import StreamHealth, StreamState
from app.infrastructure.streaming.reconnect_supervisor import ReconnectSupervisor

logger = structlog.get_logger(__name__)

_HEALTH_REPORT_INTERVAL_SECONDS = 0.25
_JOIN_TIMEOUT_SECONDS = 10.0
_TERMINATE_TIMEOUT_SECONDS = 5.0


class StreamWorker(IStreamWorker):
    """`IStreamWorker` implementation running the supervised read loop in a separate OS process.

    TD-05: one OS process per active source, since `cv2.VideoCapture`/FFmpeg
    I/O is blocking and decode work is CPU-bound — this class only owns the
    `multiprocessing.Process` handle and the two bounded, drop-oldest queues
    frames/health cross back through; the child process owns the
    `IFrameSource` and `ReconnectSupervisor` (T-024) entirely.
    """

    def __init__(
        self,
        frame_source_factory: Callable[[], IFrameSource],
        *,
        backoff_schedule: Sequence[float],
        frame_queue_max_size: int,
    ) -> None:
        self._frame_source_factory = frame_source_factory
        self._backoff_schedule = list(backoff_schedule)
        self._frame_queue_max_size = frame_queue_max_size
        self._ctx: SpawnContext = get_context("spawn")
        self._process: BaseProcess | None = None
        self._stop_event: ProcessEvent | None = None
        self._frame_queue: Any = None
        self._health_queue: Any = None
        self._latest_health = StreamHealth(state=StreamState.STOPPED)

    @property
    def pid(self) -> int | None:
        """The child process's OS PID, or `None` if not running. Not part of `IStreamWorker` — a
        concrete-class extra used to make T-023's "in a separate process" AC directly observable
        in tests, rather than exposed to use cases.
        """
        return self._process.pid if self._process is not None else None

    async def start(self) -> None:
        if self._process is not None:
            return
        self._stop_event = self._ctx.Event()
        self._frame_queue = self._ctx.Queue(maxsize=self._frame_queue_max_size)
        self._health_queue = self._ctx.Queue(maxsize=1)
        self._process = self._ctx.Process(
            target=_run_supervised_source,
            args=(
                self._frame_source_factory,
                self._backoff_schedule,
                self._frame_queue,
                self._health_queue,
                self._stop_event,
            ),
            daemon=True,
        )
        self._process.start()
        self._latest_health = StreamHealth(state=StreamState.CONNECTING)

    async def stop(self) -> None:
        if self._process is None:
            return
        process = self._process
        stop_event = self._stop_event
        assert stop_event is not None

        stop_event.set()
        await asyncio.to_thread(process.join, _JOIN_TIMEOUT_SECONDS)
        if process.is_alive():
            logger.warning("stream_worker.force_terminate", pid=process.pid)
            process.terminate()
            await asyncio.to_thread(process.join, _TERMINATE_TIMEOUT_SECONDS)

        self._process = None
        self._stop_event = None
        self._frame_queue = None
        self._health_queue = None
        self._latest_health = StreamHealth(state=StreamState.STOPPED)

    async def frames(self) -> AsyncIterator[Frame]:
        frame_queue = self._frame_queue
        if frame_queue is None:
            return
        while True:
            try:
                frame: Frame = await asyncio.to_thread(frame_queue.get, True, 0.5)
            except queue.Empty:
                if self._process is None:
                    return
                continue
            yield frame

    def health(self) -> StreamHealth:
        health_queue = self._health_queue
        if health_queue is not None:
            with contextlib.suppress(queue.Empty):
                while True:
                    self._latest_health = health_queue.get_nowait()
        return self._latest_health


def _put_drop_oldest(q: Any, item: Any) -> None:
    try:
        q.put_nowait(item)
    except queue.Full:
        with contextlib.suppress(queue.Empty):
            q.get_nowait()
        with contextlib.suppress(queue.Full):
            q.put_nowait(item)


async def _supervised_source_main(
    frame_source_factory: Callable[[], IFrameSource],
    backoff_schedule: Sequence[float],
    frame_queue: Any,
    health_queue: Any,
    stop_event: ProcessEvent,
) -> None:
    source = frame_source_factory()
    supervisor = ReconnectSupervisor(source, backoff_schedule)

    async def consume() -> None:
        async for frame in supervisor.run():
            _put_drop_oldest(frame_queue, frame)

    async def report_health() -> None:
        while True:
            _put_drop_oldest(health_queue, supervisor.health())
            await asyncio.sleep(_HEALTH_REPORT_INTERVAL_SECONDS)

    consume_task = asyncio.create_task(consume())
    health_task = asyncio.create_task(report_health())

    # Blocks this coroutine (not the event loop, via to_thread) until the
    # parent process requests shutdown — cancellation below then interrupts
    # `consume_task` at whatever point it's suspended, including mid-backoff.
    await asyncio.to_thread(stop_event.wait)

    supervisor.stop()
    consume_task.cancel()
    health_task.cancel()
    for task in (consume_task, health_task):
        with contextlib.suppress(asyncio.CancelledError):
            await task

    _put_drop_oldest(health_queue, StreamHealth(state=StreamState.STOPPED))


def _run_supervised_source(
    frame_source_factory: Callable[[], IFrameSource],
    backoff_schedule: Sequence[float],
    frame_queue: Any,
    health_queue: Any,
    stop_event: ProcessEvent,
) -> None:
    """Process entry point (must be a module-level function to be picklable under `spawn`)."""
    asyncio.run(
        _supervised_source_main(
            frame_source_factory, backoff_schedule, frame_queue, health_queue, stop_event
        )
    )
