import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import numpy as np

from app.application.use_cases.debug_stream import DebugStreamUseCase
from app.domain.entities.frame import Frame
from app.domain.value_objects.stream_health import StreamHealth, StreamState


class FakeStreamWorker:
    """A fake `IStreamWorker` double — no process, no I/O, just an in-memory frame feed."""

    def __init__(self, frame_count: int = 3) -> None:
        self.started = False
        self.stopped = False
        self._frame_count = frame_count
        self._release = asyncio.Event()

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True
        self._release.set()

    async def frames(self) -> AsyncIterator[Frame]:
        for sequence in range(self._frame_count):
            yield Frame(
                source_id="debug-mp4",
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.zeros((2, 2, 3), dtype=np.uint8),
            )
            await asyncio.sleep(0)
        await self._release.wait()

    def health(self) -> StreamHealth:
        return StreamHealth(state=StreamState.CONNECTED if self.started else StreamState.STOPPED)


async def test_status_before_start_is_stopped() -> None:
    use_case = DebugStreamUseCase(build_worker=FakeStreamWorker)
    status = use_case.status()
    assert status.health.state == StreamState.STOPPED
    assert status.latest_frame is None


async def test_start_builds_and_starts_a_worker_exactly_once() -> None:
    built: list[FakeStreamWorker] = []

    def build_worker() -> FakeStreamWorker:
        worker = FakeStreamWorker()
        built.append(worker)
        return worker

    use_case = DebugStreamUseCase(build_worker=build_worker)
    await use_case.start()
    await use_case.start()

    assert len(built) == 1
    assert built[0].started is True


async def test_status_reflects_latest_frame_metadata_once_consumed() -> None:
    use_case = DebugStreamUseCase(build_worker=lambda: FakeStreamWorker(frame_count=3))
    await use_case.start()

    for _ in range(50):
        latest = use_case.status().latest_frame
        if latest is not None and latest.sequence == 2:
            break
        await asyncio.sleep(0)

    status = use_case.status()
    assert status.health.state == StreamState.CONNECTED
    assert status.latest_frame is not None
    assert status.latest_frame.sequence == 2
    assert status.latest_frame.image_shape == (2, 2, 3)

    await use_case.stop()
    assert use_case.status().health.state == StreamState.STOPPED
    assert use_case.status().latest_frame is None
