from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np

from app.application.use_cases.run_analytics_pipeline import RunAnalyticsPipelineUseCase
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from tests.fixtures.streaming.bounded_frame_source import BoundedFrameSource


class _FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[DetectionEvent] = []

    async def publish(self, event: DetectionEvent) -> None:
        self.published.append(event)

    def subscribe(self, handler: object) -> None:  # pragma: no cover - unused by these tests
        raise NotImplementedError


def _noop_event(frame: Frame) -> list[DetectionEvent]:
    return [
        DetectionEvent(
            camera_id=uuid4(),
            event_type="test.event",
            occurred_at=datetime.now(UTC),
            confidence=1.0,
            metadata={"sequence": frame.sequence},
        )
    ]


async def _process_none(frame: Frame) -> list[DetectionEvent]:
    return []


async def test_execute_starts_and_stops_the_frame_source() -> None:
    source = BoundedFrameSource(frame_count=3)
    publisher = _FakeEventPublisher()
    use_case = RunAnalyticsPipelineUseCase(source, _process_none, publisher)

    await use_case.execute()

    assert source.start_calls == 1
    assert source.stop_calls == 1


async def test_execute_processes_every_frame_and_publishes_events() -> None:
    source = BoundedFrameSource(frame_count=3)
    publisher = _FakeEventPublisher()
    processed: list[Frame] = []

    async def process(frame: Frame) -> list[DetectionEvent]:
        processed.append(frame)
        return _noop_event(frame)

    use_case = RunAnalyticsPipelineUseCase(source, process, publisher)
    await use_case.execute()

    assert [frame.sequence for frame in processed] == [0, 1, 2]
    assert len(publisher.published) == 3


async def test_disable_stops_processing_without_touching_the_frame_source() -> None:
    source = BoundedFrameSource(frame_count=5)
    publisher = _FakeEventPublisher()
    processed: list[Frame] = []

    async def process(frame: Frame) -> list[DetectionEvent]:
        processed.append(frame)
        if frame.sequence == 1:
            use_case.disable()
        return _noop_event(frame)

    use_case = RunAnalyticsPipelineUseCase(source, process, publisher)
    await use_case.execute()

    # Frames 0 and 1 were processed (disable happens while handling frame 1);
    # frames 2-4 still flow through `frame_source.frames()` (proving
    # disabling never restarts/stops the source) but are skipped, not
    # processed/published.
    assert [frame.sequence for frame in processed] == [0, 1]
    assert len(publisher.published) == 2
    assert source.start_calls == 1
    assert source.stop_calls == 1


class _ReEnablingSource:
    """A fake `IFrameSource` that re-enables the use case mid-stream (simulating
    an external `enable()` call arriving, e.g. via `AnalyticsSessionRegistry`,
    while frames are still flowing)."""

    def __init__(self, *, reenable_at: int) -> None:
        self._use_case: RunAnalyticsPipelineUseCase | None = None
        self._reenable_at = reenable_at
        self.start_calls = 0
        self.stop_calls = 0

    def bind(self, use_case: RunAnalyticsPipelineUseCase) -> None:
        self._use_case = use_case

    @property
    def source_id(self) -> str:
        return "reenable-fake"

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def frames(self) -> AsyncIterator[Frame]:
        assert self._use_case is not None, "bind() must be called before frames() is iterated"
        for sequence in range(4):
            if sequence == self._reenable_at:
                self._use_case.enable()
            yield Frame(
                source_id=self.source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.zeros((2, 2, 3), dtype=np.uint8),
            )


async def test_enable_after_disable_resumes_processing() -> None:
    publisher = _FakeEventPublisher()
    processed: list[Frame] = []

    async def process(frame: Frame) -> list[DetectionEvent]:
        processed.append(frame)
        if frame.sequence == 0:
            use_case.disable()
        return []

    source = _ReEnablingSource(reenable_at=2)
    use_case = RunAnalyticsPipelineUseCase(source, process, publisher)
    source.bind(use_case)

    await use_case.execute()

    # Frame 0: processed, then disabled. Frame 1: skipped (disabled). Frame 2:
    # the source re-enables just before yielding it, so 2 and 3 are processed.
    assert [frame.sequence for frame in processed] == [0, 2, 3]


async def test_request_stop_ends_the_loop_early() -> None:
    source = BoundedFrameSource(frame_count=10)
    publisher = _FakeEventPublisher()
    processed: list[Frame] = []

    async def process(frame: Frame) -> list[DetectionEvent]:
        processed.append(frame)
        if frame.sequence == 1:
            use_case.request_stop()
        return []

    use_case = RunAnalyticsPipelineUseCase(source, process, publisher)
    await use_case.execute()

    assert [frame.sequence for frame in processed] == [0, 1]
    assert source.stop_calls == 1
