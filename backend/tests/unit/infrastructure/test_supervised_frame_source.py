from app.infrastructure.streaming.supervised_frame_source import SupervisedFrameSource
from tests.fixtures.streaming.flaky_frame_source import FlakyFrameSource


async def test_source_id_proxies_the_wrapped_source() -> None:
    source = SupervisedFrameSource(FlakyFrameSource("wrapped"), backoff_schedule=[0.01])
    assert source.source_id == "wrapped"


async def test_frames_are_proxied_from_the_wrapped_source() -> None:
    inner = FlakyFrameSource("wrapped")
    source = SupervisedFrameSource(inner, backoff_schedule=[0.01])
    await source.start()

    frames = []
    async for frame in source.frames():
        frames.append(frame)
        if len(frames) == 3:
            await source.stop()

    assert [frame.sequence for frame in frames] == [0, 1, 2]


async def test_reconnects_through_a_transient_start_failure() -> None:
    inner = FlakyFrameSource("wrapped", fail_start_times=2)
    source = SupervisedFrameSource(inner, backoff_schedule=[0.01, 0.01])
    await source.start()

    frames = []
    async for frame in source.frames():
        frames.append(frame)
        if len(frames) == 1:
            await source.stop()

    assert inner.start_attempts == 3
    assert len(frames) == 1
