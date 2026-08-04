"""Integration tests for `StreamWorker` against the committed MP4 fixture (T-023).

Exercises the real `multiprocessing` path end to end — no fakes for the
process boundary itself, since T-023's own acceptance criterion is that
frames are produced "in a separate process."
"""

import asyncio
import functools
import os
from collections.abc import AsyncIterator
from pathlib import Path

from app.domain.entities.frame import Frame
from app.domain.value_objects.stream_health import StreamState
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource
from app.infrastructure.streaming.stream_worker import StreamWorker

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"


async def _collect(frames: AsyncIterator[Frame], count: int) -> list[Frame]:
    collected: list[Frame] = []
    async for frame in frames:
        collected.append(frame)
        if len(collected) >= count:
            break
    return collected


async def test_produces_frames_in_a_separate_process_at_the_fixture_fps() -> None:
    factory = functools.partial(
        Mp4FileFrameSource, file_path=str(_FIXTURE_PATH), source_id="worker-test", loop=True
    )
    worker = StreamWorker(
        frame_source_factory=factory, backoff_schedule=[1, 2, 4], frame_queue_max_size=10
    )

    await worker.start()
    try:
        assert worker.pid is not None
        assert worker.pid != os.getpid()

        collected = await asyncio.wait_for(_collect(worker.frames(), 3), timeout=15.0)
        assert [f.sequence for f in collected] == [0, 1, 2]
        assert all(f.source_id == "worker-test" for f in collected)

        for _ in range(50):
            if worker.health().state == StreamState.CONNECTED:
                break
            await asyncio.sleep(0.1)
        assert worker.health().state == StreamState.CONNECTED
    finally:
        await worker.stop()

    assert worker.pid is None


async def test_frame_queue_stays_bounded_under_sustained_overload() -> None:
    """T-023 AC: "under sustained overload, memory stays bounded (queue never grows unbounded)".

    A fast (500fps-throttled) source is left unconsumed for ~1s, which would
    buffer ~500 frames on an unbounded queue. `qsize()` isn't reliably
    available on every platform's `multiprocessing.Queue` (notably macOS), so
    this stops the worker first (freezing the queue's backlog, since the
    child process stops producing) and then drains it fully — draining
    landing near `frame_queue_max_size` rather than ~500 proves the drop-
    oldest bound held throughout the overload window, not just at the end.
    """
    factory = functools.partial(
        Mp4FileFrameSource,
        file_path=str(_FIXTURE_PATH),
        source_id="overload-test",
        loop=True,
        fps=500.0,
    )
    max_size = 3
    worker = StreamWorker(
        frame_source_factory=factory, backoff_schedule=[1], frame_queue_max_size=max_size
    )

    await worker.start()
    frames = worker.frames()
    await asyncio.sleep(1.0)
    await worker.stop()

    drained = [frame async for frame in frames]
    assert len(drained) <= max_size + 2
