"""Integration tests against the committed MP4 fixture (T-021), per AGENTS.md
Testing Expectations: infrastructure adapters are tested with real I/O against
`backend/tests/fixtures/sample.mp4`, not fakes.
"""

import time
from pathlib import Path

import pytest

from app.domain.exceptions import FrameSourceUnavailableError
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"
_FIXTURE_FPS = 10.0
_FIXTURE_FRAME_COUNT = 50


async def test_yields_frames_at_the_expected_throttled_rate() -> None:
    source = Mp4FileFrameSource(str(_FIXTURE_PATH), source_id="sample", loop=False)
    await source.start()
    try:
        frames_wanted = 5
        started_at = time.monotonic()
        frames = source.frames()
        collected = [await anext(frames) for _ in range(frames_wanted)]
        elapsed = time.monotonic() - started_at
    finally:
        await source.stop()

    assert [f.sequence for f in collected] == list(range(frames_wanted))
    for frame in collected:
        assert frame.source_id == "sample"
        assert frame.image.shape == (240, 320, 3)

    expected_min = (frames_wanted - 1) / _FIXTURE_FPS * 0.5
    expected_max = (frames_wanted - 1) / _FIXTURE_FPS * 4
    assert expected_min <= elapsed <= expected_max


async def test_loops_past_end_of_file_when_loop_is_true() -> None:
    source = Mp4FileFrameSource(str(_FIXTURE_PATH), source_id="sample", loop=True, fps=1000.0)
    await source.start()
    try:
        frames = source.frames()
        collected = [await anext(frames) for _ in range(_FIXTURE_FRAME_COUNT + 5)]
    finally:
        await source.stop()

    assert len(collected) == _FIXTURE_FRAME_COUNT + 5


async def test_ends_at_eof_when_loop_is_false() -> None:
    source = Mp4FileFrameSource(str(_FIXTURE_PATH), source_id="sample", loop=False, fps=1000.0)
    await source.start()
    try:
        collected = [frame async for frame in source.frames()]
    finally:
        await source.stop()

    assert len(collected) == _FIXTURE_FRAME_COUNT


async def test_start_raises_frame_source_unavailable_for_a_missing_file() -> None:
    source = Mp4FileFrameSource("/nonexistent/path/does-not-exist.mp4", source_id="missing")
    with pytest.raises(FrameSourceUnavailableError):
        await source.start()
