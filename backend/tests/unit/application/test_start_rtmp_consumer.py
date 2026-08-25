import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import numpy as np
import pytest

from app.application.ports.stream_worker import IStreamWorker
from app.application.use_cases.start_rtmp_consumer import StartRtmpConsumerUseCase
from app.domain.entities.frame import Frame
from app.domain.exceptions import FrameSourceUnavailableError
from app.domain.value_objects.stream_health import StreamHealth, StreamState


class FakeStreamWorker(IStreamWorker):
    """A fake `IStreamWorker` double — no process, no I/O (mirrors
    `test_start_demo_stream.py`'s identical fake)."""

    def __init__(self, frame_count: int = 5, width: int = 8, height: int = 6) -> None:
        self.started = False
        self.stopped = False
        self._frame_count = frame_count
        self._width = width
        self._height = height
        self._release = asyncio.Event()

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True
        self._release.set()

    async def frames(self) -> AsyncIterator[Frame]:
        for sequence in range(self._frame_count):
            yield Frame(
                source_id="rtmp-demo-consumer",
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.zeros((self._height, self._width, 3), dtype=np.uint8),
            )
            await asyncio.sleep(0.01)
        await self._release.wait()

    def health(self) -> StreamHealth:
        return StreamHealth(state=StreamState.CONNECTED if self.started else StreamState.STOPPED)


def _build_use_case(
    built: list[FakeStreamWorker] | None = None, **worker_kwargs: int
) -> StartRtmpConsumerUseCase:
    built = built if built is not None else []

    def build_stream_worker() -> FakeStreamWorker:
        worker = FakeStreamWorker(**worker_kwargs)
        built.append(worker)
        return worker

    return StartRtmpConsumerUseCase(build_stream_worker=build_stream_worker)


async def test_health_before_start_is_stopped() -> None:
    use_case = _build_use_case()
    assert use_case.health().state == StreamState.STOPPED


async def test_diagnostics_before_start_is_empty() -> None:
    use_case = _build_use_case()
    diagnostics = use_case.diagnostics()
    assert diagnostics.resolution is None
    assert diagnostics.observed_fps is None


async def test_frames_raises_when_not_started() -> None:
    use_case = _build_use_case()
    with pytest.raises(FrameSourceUnavailableError):
        use_case.frames()


async def test_execute_starts_worker_and_is_idempotent() -> None:
    built: list[FakeStreamWorker] = []
    use_case = _build_use_case(built)

    await use_case.execute()
    await use_case.execute()

    assert len(built) == 1
    assert built[0].started is True
    assert use_case.health().state == StreamState.CONNECTED


async def test_diagnostics_reports_observed_resolution_and_fps_after_frames() -> None:
    use_case = _build_use_case(width=16, height=9, frame_count=5)
    await use_case.execute()

    viewer = use_case.frames()
    for _ in range(3):
        await anext(viewer)

    diagnostics = use_case.diagnostics()
    assert diagnostics.resolution == (16, 9)
    assert diagnostics.observed_fps is not None
    assert diagnostics.observed_fps > 0

    await use_case.stop()


async def test_frames_fan_out_to_multiple_viewers() -> None:
    use_case = _build_use_case()
    await use_case.execute()

    viewer_a = use_case.frames()
    viewer_b = use_case.frames()

    first_a = await anext(viewer_a)
    first_b = await anext(viewer_b)

    assert first_a.sequence == first_b.sequence == 0
    assert first_a.source_id == "rtmp-demo-consumer"

    await use_case.stop()
    assert use_case.health().state == StreamState.STOPPED


async def test_stop_is_a_no_op_when_never_started() -> None:
    use_case = _build_use_case()
    await use_case.stop()  # must not raise


async def test_stop_all_stops_the_running_worker() -> None:
    built: list[FakeStreamWorker] = []
    use_case = _build_use_case(built)
    await use_case.execute()

    await use_case.stop_all()

    assert built[0].stopped is True
    assert use_case.health().state == StreamState.STOPPED
