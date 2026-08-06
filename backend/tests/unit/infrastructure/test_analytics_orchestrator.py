from datetime import UTC, datetime
from typing import Any

import numpy as np

from app.application.ports.detector_plugin import IDetectorPlugin
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.infrastructure.analytics.orchestrator import AnalyticsOrchestrator


def _frame(sequence: int = 0) -> Frame:
    return Frame(
        source_id="test",
        sequence=sequence,
        timestamp=datetime.now(UTC),
        image=np.zeros((2, 2, 3), dtype=np.uint8),
    )


class _RecordingPlugin(IDetectorPlugin):
    def __init__(self, plugin_id: str, events: list[DetectionEvent] | None = None) -> None:
        self._plugin_id = plugin_id
        self._events = events or []
        self.calls: list[tuple[Frame, dict[str, Any]]] = []

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        self.calls.append((frame, context))
        return list(self._events)


async def test_process_invokes_every_plugin_once_per_call() -> None:
    plugin_a = _RecordingPlugin("a")
    plugin_b = _RecordingPlugin("b")
    orchestrator = AnalyticsOrchestrator([plugin_a, plugin_b])

    frame = _frame()
    await orchestrator.process(frame)

    assert len(plugin_a.calls) == 1
    assert len(plugin_b.calls) == 1
    assert plugin_a.calls[0][0] is frame
    assert plugin_b.calls[0][0] is frame


async def test_process_collects_events_from_every_plugin() -> None:
    from uuid import uuid4

    event_a = DetectionEvent(
        camera_id=uuid4(), event_type="a.event", occurred_at=datetime.now(UTC), confidence=1.0
    )
    event_b = DetectionEvent(
        camera_id=uuid4(), event_type="b.event", occurred_at=datetime.now(UTC), confidence=1.0
    )
    orchestrator = AnalyticsOrchestrator(
        [_RecordingPlugin("a", [event_a]), _RecordingPlugin("b", [event_b])]
    )

    events = await orchestrator.process(_frame())

    assert events == [event_a, event_b]


async def test_plugins_share_one_context_across_calls() -> None:
    plugin = _RecordingPlugin("a")
    orchestrator = AnalyticsOrchestrator([plugin])

    await orchestrator.process(_frame(sequence=0))
    await orchestrator.process(_frame(sequence=1))

    first_context = plugin.calls[0][1]
    second_context = plugin.calls[1][1]
    assert first_context is second_context


async def test_no_plugins_means_no_events() -> None:
    orchestrator = AnalyticsOrchestrator([])
    assert await orchestrator.process(_frame()) == []


async def test_enabled_plugin_ids_none_runs_every_plugin() -> None:
    plugin_a = _RecordingPlugin("a")
    plugin_b = _RecordingPlugin("b")
    orchestrator = AnalyticsOrchestrator([plugin_a, plugin_b])

    await orchestrator.process(_frame(), enabled_plugin_ids=None)

    assert len(plugin_a.calls) == 1
    assert len(plugin_b.calls) == 1


async def test_enabled_plugin_ids_skips_plugins_not_in_the_set() -> None:
    plugin_a = _RecordingPlugin("a")
    plugin_b = _RecordingPlugin("b")
    orchestrator = AnalyticsOrchestrator([plugin_a, plugin_b])

    await orchestrator.process(_frame(), enabled_plugin_ids=frozenset({"a"}))

    assert len(plugin_a.calls) == 1
    assert len(plugin_b.calls) == 0


async def test_enabled_plugin_ids_empty_set_skips_every_plugin() -> None:
    plugin_a = _RecordingPlugin("a")
    orchestrator = AnalyticsOrchestrator([plugin_a])

    events = await orchestrator.process(_frame(), enabled_plugin_ids=frozenset())

    assert events == []
    assert len(plugin_a.calls) == 0


async def test_enabled_plugin_ids_skipped_plugin_gets_no_context_from_earlier_plugins() -> None:
    upstream = _RecordingPlugin("upstream")
    downstream = _RecordingPlugin("downstream")
    orchestrator = AnalyticsOrchestrator([upstream, downstream])

    await orchestrator.process(_frame(), enabled_plugin_ids=frozenset({"downstream"}))

    assert len(upstream.calls) == 0
    assert len(downstream.calls) == 1
