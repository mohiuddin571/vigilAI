"""T-024's required test: proves the reconnect/backoff sequence against a fake flaky
`IFrameSource`, with no real I/O and no real waiting (a fake `sleep` records delays
instead of actually sleeping). Permanent per docs/TASK_BACKLOG.md T-024 — must never
be deleted or weakened, mirroring T-086's permanence for the analytics pipeline.
"""

import pytest

from app.domain.value_objects.stream_health import StreamState
from app.infrastructure.streaming.reconnect_supervisor import ReconnectSupervisor
from tests.fixtures.streaming.flaky_frame_source import FlakyFrameSource


class _RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


async def test_backoff_sequence_matches_configured_schedule() -> None:
    source = FlakyFrameSource(fail_start_times=4)
    sleeper = _RecordingSleeper()
    supervisor = ReconnectSupervisor(source, backoff_schedule=[1, 2, 4, 8, 16, 30], sleep=sleeper)

    frames = supervisor.run()
    frame = await anext(frames)

    assert sleeper.delays == [1, 2, 4, 8]
    assert frame.sequence == 0
    assert supervisor.health().state == StreamState.CONNECTED
    assert supervisor.health().consecutive_failures == 0

    supervisor.stop()


async def test_backoff_caps_at_last_schedule_value_once_exhausted() -> None:
    source = FlakyFrameSource(fail_start_times=10)
    sleeper = _RecordingSleeper()
    supervisor = ReconnectSupervisor(source, backoff_schedule=[1, 2, 4], sleep=sleeper)

    frames = supervisor.run()
    await anext(frames)

    assert sleeper.delays == [1, 2, 4, 4, 4, 4, 4, 4, 4, 4]
    supervisor.stop()


async def test_mid_stream_disconnect_triggers_reconnect_and_resumes() -> None:
    source = FlakyFrameSource(fail_after_frames=2)
    sleeper = _RecordingSleeper()
    supervisor = ReconnectSupervisor(source, backoff_schedule=[1, 2, 4], sleep=sleeper)

    frames = supervisor.run()
    received = [await anext(frames), await anext(frames)]
    resumed = await anext(frames)

    assert [f.sequence for f in received] == [0, 1]
    assert sleeper.delays == [1]
    assert resumed.sequence == 0  # a fresh session after reconnect

    supervisor.stop()


async def test_last_error_clears_after_a_successful_reconnect() -> None:
    source = FlakyFrameSource(fail_start_times=2)
    sleeper = _RecordingSleeper()
    supervisor = ReconnectSupervisor(source, backoff_schedule=[1, 2, 4], sleep=sleeper)

    frames = supervisor.run()
    await anext(frames)

    assert supervisor.health().last_error is None
    supervisor.stop()


async def test_stop_ends_the_run_loop() -> None:
    source = FlakyFrameSource()
    supervisor = ReconnectSupervisor(source, backoff_schedule=[1])

    frames = supervisor.run()
    await anext(frames)
    supervisor.stop()

    with pytest.raises(StopAsyncIteration):
        await anext(frames)

    assert supervisor.health().state == StreamState.STOPPED


def test_rejects_empty_backoff_schedule() -> None:
    with pytest.raises(ValueError):
        ReconnectSupervisor(FlakyFrameSource(), backoff_schedule=[])
