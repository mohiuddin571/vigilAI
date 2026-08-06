import asyncio
import contextlib
from collections import defaultdict
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from app.application.ports.demo_video_repository import IDemoVideoRepository
from app.application.ports.stream_worker import IStreamWorker
from app.domain.entities.frame import Frame
from app.domain.exceptions import DemoVideoNotFoundError, FrameSourceUnavailableError
from app.domain.value_objects.stream_health import StreamHealth, StreamState


class _StreamHandle:
    """A small, deliberate duplicate of `start_live_stream.py`'s private
    `_StreamHandle` (same one-worker/many-viewers fan-out shape) — not
    imported across modules per this repo's own small-duplication precedent
    for near-identical-but-not-shared private helpers (docs/TECHNICAL_DECISIONS.md
    TD-25/TD-29)."""

    def __init__(self, worker: IStreamWorker) -> None:
        self.worker = worker
        self._latest_frame: Frame | None = None
        self._condition = asyncio.Condition()
        self._stopped = False
        self.consume_task: asyncio.Task[None] | None = None

    async def start_consuming(self) -> None:
        self.consume_task = asyncio.create_task(self._consume())

    async def _consume(self) -> None:
        async for frame in self.worker.frames():
            async with self._condition:
                self._latest_frame = frame
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

    async def stop(self) -> None:
        if self.consume_task is not None:
            self.consume_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.consume_task
            self.consume_task = None
        await self.worker.stop()
        async with self._condition:
            self._stopped = True
            self._condition.notify_all()


class StartDemoStreamUseCase:
    """Start/stop/observe streams over the demo video library (M17, T-206).

    A deliberate small duplicate of `StartLiveStreamUseCase`, simplified:
    no `ICameraGateway` reachability check (there's no camera to reach —
    just a local file) and no `StreamProfile` selection, and keyed by a
    plain `str` `video_id` (a `DemoVideo.id` slug) instead of a `UUID`
    `camera_id`. Kept separate rather than generalizing `StartLiveStreamUseCase`
    itself over both key types — same "small duplication over cross-cutting
    abstraction" precedent `_select_primary_stream_profile` already set
    (docs/TECHNICAL_DECISIONS.md TD-25).

    Preconditions: `video_id` identifies a file currently present in the
    configured demo videos directory (`IDemoVideoRepository.resolve_path`).

    Raises:
        DemoVideoNotFoundError: `video_id` doesn't resolve to a file.
    """

    def __init__(
        self,
        demo_video_repository: IDemoVideoRepository,
        build_stream_worker: Callable[[str, Path], IStreamWorker],
    ) -> None:
        self._demo_video_repository = demo_video_repository
        self._build_stream_worker = build_stream_worker
        self._streams: dict[str, _StreamHandle] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def execute(self, video_id: str) -> None:
        async with self._locks[video_id]:
            if video_id in self._streams:
                return

            path = self._demo_video_repository.resolve_path(video_id)
            if path is None:
                raise DemoVideoNotFoundError(f"No demo video with id {video_id!r}")

            worker = self._build_stream_worker(video_id, path)
            await worker.start()
            handle = _StreamHandle(worker)
            await handle.start_consuming()
            self._streams[video_id] = handle

    async def stop(self, video_id: str) -> None:
        async with self._locks[video_id]:
            handle = self._streams.pop(video_id, None)
            if handle is None:
                return
            await handle.stop()

    async def stop_all(self) -> None:
        """Stop every currently running demo Stream Worker — called from the
        composition root's graceful-shutdown path, same orphaned-subprocess
        concern `StartLiveStreamUseCase.stop_all`'s docstring documents."""
        for video_id in list(self._streams):
            await self.stop(video_id)

    def frames(self, video_id: str) -> AsyncIterator[Frame]:
        handle = self._streams.get(video_id)
        if handle is None:
            raise FrameSourceUnavailableError(f"No demo stream is running for video {video_id}")
        return handle.frames()

    def health(self, video_id: str) -> StreamHealth:
        handle = self._streams.get(video_id)
        if handle is None:
            return StreamHealth(state=StreamState.STOPPED)
        return handle.health()
