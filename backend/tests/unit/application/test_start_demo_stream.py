import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from app.application.ports.demo_video_repository import IDemoVideoRepository
from app.application.use_cases.start_demo_stream import StartDemoStreamUseCase
from app.domain.entities.demo_video import DemoVideo
from app.domain.entities.frame import Frame
from app.domain.exceptions import DemoVideoNotFoundError, FrameSourceUnavailableError
from app.domain.value_objects.stream_health import StreamHealth, StreamState


class FakeDemoVideoRepository(IDemoVideoRepository):
    def __init__(self, paths: dict[str, Path]) -> None:
        self._paths = paths

    def list_videos(self) -> list[DemoVideo]:
        return [DemoVideo(id=video_id, filename=path.name) for video_id, path in self._paths.items()]

    def resolve_path(self, video_id: str) -> Path | None:
        return self._paths.get(video_id)


class FakeStreamWorker:
    """A fake `IStreamWorker` double — no process, no I/O (mirrors
    `test_start_live_stream.py`'s identical fake)."""

    def __init__(self, source_id: str, frame_count: int = 3) -> None:
        self.source_id = source_id
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
                source_id=self.source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.zeros((2, 2, 3), dtype=np.uint8),
            )
            await asyncio.sleep(0)
        await self._release.wait()

    def health(self) -> StreamHealth:
        return StreamHealth(state=StreamState.CONNECTED if self.started else StreamState.STOPPED)


def _build_use_case(
    paths: dict[str, Path], built_workers: list[FakeStreamWorker] | None = None
) -> StartDemoStreamUseCase:
    built_workers = built_workers if built_workers is not None else []

    def build_stream_worker(video_id: str, file_path: Path) -> FakeStreamWorker:
        worker = FakeStreamWorker(source_id=video_id)
        built_workers.append(worker)
        return worker

    return StartDemoStreamUseCase(
        demo_video_repository=FakeDemoVideoRepository(paths),
        build_stream_worker=build_stream_worker,  # type: ignore[arg-type]
    )


async def test_execute_raises_demo_video_not_found_for_unknown_id() -> None:
    use_case = _build_use_case({})
    with pytest.raises(DemoVideoNotFoundError):
        await use_case.execute("unknown")


async def test_execute_starts_worker_and_is_idempotent() -> None:
    built: list[FakeStreamWorker] = []
    use_case = _build_use_case({"parking-lot": Path("/videos/parking-lot.mp4")}, built)

    await use_case.execute("parking-lot")
    await use_case.execute("parking-lot")

    assert len(built) == 1
    assert built[0].started is True
    assert use_case.health("parking-lot").state == StreamState.CONNECTED


async def test_frames_fan_out_to_multiple_viewers() -> None:
    use_case = _build_use_case({"parking-lot": Path("/videos/parking-lot.mp4")})
    await use_case.execute("parking-lot")

    viewer_a = use_case.frames("parking-lot")
    viewer_b = use_case.frames("parking-lot")

    first_a = await anext(viewer_a)
    first_b = await anext(viewer_b)

    assert first_a.sequence == first_b.sequence == 0
    assert first_a.source_id == "parking-lot"

    await use_case.stop("parking-lot")
    assert use_case.health("parking-lot").state == StreamState.STOPPED


async def test_frames_raises_when_no_stream_is_running() -> None:
    use_case = _build_use_case({"parking-lot": Path("/videos/parking-lot.mp4")})
    with pytest.raises(FrameSourceUnavailableError):
        use_case.frames("parking-lot")


async def test_stop_is_a_no_op_for_a_stream_that_was_never_started() -> None:
    use_case = _build_use_case({})
    await use_case.stop("unknown")  # must not raise


async def test_stop_all_stops_every_running_worker() -> None:
    built: list[FakeStreamWorker] = []
    use_case = _build_use_case(
        {"a": Path("/videos/a.mp4"), "b": Path("/videos/b.mp4")},
        built,
    )

    await use_case.execute("a")
    await use_case.execute("b")

    await use_case.stop_all()

    assert all(worker.stopped for worker in built)
    assert use_case.health("a").state == StreamState.STOPPED
    assert use_case.health("b").state == StreamState.STOPPED


async def test_stop_all_is_a_no_op_with_nothing_running() -> None:
    use_case = _build_use_case({})
    await use_case.stop_all()  # must not raise
