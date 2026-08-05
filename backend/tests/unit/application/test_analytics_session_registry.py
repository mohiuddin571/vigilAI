import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np

from app.application.use_cases.analytics_session_registry import AnalyticsSessionRegistry
from app.application.use_cases.run_analytics_pipeline import RunAnalyticsPipelineUseCase
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame


class _FakeSource:
    """Yields a fixed number of frames, then blocks (until released) rather than
    ending — so a test can assert "the source was never stopped/restarted"
    across an enable/disable cycle without racing a naturally-ending generator."""

    def __init__(self, source_id: str, frame_count: int = 10) -> None:
        self.source_id = source_id
        self.start_calls = 0
        self.stop_calls = 0
        self._frame_count = frame_count
        self._release = asyncio.Event()

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1
        self._release.set()

    def release(self) -> None:
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


class _FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[DetectionEvent] = []

    async def publish(self, event: DetectionEvent) -> None:
        self.published.append(event)

    def subscribe(self, handler: object) -> None:  # pragma: no cover - unused by these tests
        raise NotImplementedError


def _event(frame: Frame) -> list[DetectionEvent]:
    return [
        DetectionEvent(
            camera_id=uuid4(),
            event_type="test.event",
            occurred_at=datetime.now(UTC),
            confidence=1.0,
            metadata={"sequence": frame.sequence},
        )
    ]


async def test_enable_starts_a_session_and_events_are_published() -> None:
    publisher = _FakeEventPublisher()
    sources: dict[str, _FakeSource] = {}

    async def process(frame: Frame) -> list[DetectionEvent]:
        return _event(frame)

    async def build_use_case(source_id: str) -> RunAnalyticsPipelineUseCase:
        source = _FakeSource(source_id)
        sources[source_id] = source
        return RunAnalyticsPipelineUseCase(source, process, publisher)  # type: ignore[arg-type]

    registry = AnalyticsSessionRegistry(build_use_case)

    await registry.enable("mp4-demo")
    for _ in range(1000):
        if len(publisher.published) >= 3:
            break
        await asyncio.sleep(0)

    assert registry.is_enabled("mp4-demo") is True
    assert sources["mp4-demo"].start_calls == 1
    assert len(publisher.published) >= 3

    sources["mp4-demo"].release()


async def test_enable_twice_does_not_start_a_second_session() -> None:
    sources: dict[str, _FakeSource] = {}

    async def build_use_case(source_id: str) -> RunAnalyticsPipelineUseCase:
        source = _FakeSource(source_id)
        sources[source_id] = source
        return RunAnalyticsPipelineUseCase(
            source,  # type: ignore[arg-type]
            lambda frame: _async_none(),
            _FakeEventPublisher(),  # type: ignore[arg-type]
        )

    registry = AnalyticsSessionRegistry(build_use_case)

    await registry.enable("mp4-demo")
    await registry.enable("mp4-demo")

    assert len(sources) == 1

    sources["mp4-demo"].release()


async def _async_none() -> list[DetectionEvent]:
    return []


async def test_disable_stops_new_events_without_restarting_the_source() -> None:
    """T-085's Definition of Done, verified directly: toggling analytics off
    stops new events, but the underlying source is never stopped/restarted."""
    publisher = _FakeEventPublisher()
    sources: dict[str, _FakeSource] = {}
    registry_holder: dict[str, AnalyticsSessionRegistry] = {}

    async def process(frame: Frame) -> list[DetectionEvent]:
        if frame.sequence == 2:
            await registry_holder["registry"].disable("mp4-demo")
        return _event(frame)

    async def build_use_case(source_id: str) -> RunAnalyticsPipelineUseCase:
        source = _FakeSource(source_id)
        sources[source_id] = source
        return RunAnalyticsPipelineUseCase(source, process, publisher)  # type: ignore[arg-type]

    registry = AnalyticsSessionRegistry(build_use_case)
    registry_holder["registry"] = registry

    await registry.enable("mp4-demo")
    # Let the background task run past the frame that disables analytics and
    # drain the rest of the (finite, but not yet exhausted) fake source.
    for _ in range(1000):
        await asyncio.sleep(0)

    assert registry.is_enabled("mp4-demo") is False
    # Frames 0, 1, 2 processed before/at the disable call -> 3 events.
    assert len(publisher.published) == 3
    source = sources["mp4-demo"]
    assert source.start_calls == 1
    assert source.stop_calls == 0  # never stopped/restarted by disable()

    source.release()


async def _fail_build_use_case(source_id: str) -> RunAnalyticsPipelineUseCase:
    raise AssertionError("build_use_case must not be called for disable() with no session")


async def test_disable_on_a_source_with_no_session_is_a_no_op() -> None:
    registry = AnalyticsSessionRegistry(_fail_build_use_case)
    await registry.disable("never-enabled")  # must not raise
    assert registry.is_enabled("never-enabled") is False
