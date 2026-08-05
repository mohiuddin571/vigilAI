"""T-113: `LoiteringDetector`'s dwell timer + de-dup, plus its context-based
handoff from `YoloObjectDetector` (docs/TECHNICAL_DECISIONS.md TD-27/TD-28).

Uses synthetic track data (constructed `Frame`/`DetectionEvent`/`AnalyticsZone`
fixtures), not real footage — the same reasoning `test_yolo_detector_integration.py`
and `test_color_detector_integration.py` already document: `sample.mp4` is a
synthetic clip with no real loitering scenario in it (docs/TECHNICAL_DECISIONS.md
TD-20/TD-25), and the milestone's own acceptance criterion ("one event per
qualifying dwell period, not per frame") is exactly what synthetic,
precisely-timed frames let this test assert deterministically.

A single `context` dict is reused across every `process()` call within a test
(not rebuilt each iteration) — this mirrors how `AnalyticsOrchestrator` reuses
one `self._context` for the lifetime of a pipeline run, which is what lets
`LoiteringDetector`'s cross-frame dwell state actually accumulate.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import numpy as np

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.domain.value_objects.bounding_box import BoundingBox
from app.infrastructure.analytics.loitering_detector import (
    _TRACK_STATE_CONTEXT_KEY,
    LoiteringDetector,
)
from app.infrastructure.analytics.yolo_detector import EVENTS_BY_SOURCE_CONTEXT_KEY

_BLANK_IMAGE = np.zeros((20, 20, 3), dtype=np.uint8)
_BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)
_FULL_FRAME_ZONE_POLYGON = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
_LEFT_HALF_ZONE_POLYGON = [(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)]
_CENTER_BOX = BoundingBox(x_min=0.4, y_min=0.4, x_max=0.6, y_max=0.6)


class _FakeZoneRepository(IAnalyticsZoneRepository):
    def __init__(self, zones: list[AnalyticsZone]) -> None:
        self._zones = zones

    async def add(self, zone: AnalyticsZone) -> None:
        self._zones.append(zone)

    async def get(self, zone_id: UUID) -> AnalyticsZone | None:
        return next((z for z in self._zones if z.id == zone_id), None)

    async def list_by_camera(self, camera_id: UUID) -> list[AnalyticsZone]:
        return [zone for zone in self._zones if zone.camera_id == camera_id]

    async def update(self, zone: AnalyticsZone) -> None:
        self._zones = [zone if z.id == zone.id else z for z in self._zones]

    async def delete(self, zone_id: UUID) -> None:
        self._zones = [z for z in self._zones if z.id != zone_id]


def _frame(second: float, source_id: str = "mp4-demo", sequence: int = 0) -> Frame:
    return Frame(
        source_id=source_id,
        sequence=sequence,
        timestamp=_BASE_TIME + timedelta(seconds=second),
        image=_BLANK_IMAGE,
    )


def _source_event(
    frame: Frame,
    camera_id: UUID,
    track_id: int | None,
    box: BoundingBox | None = _CENTER_BOX,
) -> DetectionEvent:
    return DetectionEvent(
        camera_id=camera_id,
        event_type="object_detection.person",
        occurred_at=frame.timestamp,
        confidence=0.9,
        bounding_box=box,
        metadata={
            "source_id": frame.source_id,
            "frame_sequence": frame.sequence,
            "class_label": "person",
            "track_id": track_id,
        },
    )


def _set_context_events(context: dict, frame: Frame, events: list[DetectionEvent]) -> None:
    context.setdefault(EVENTS_BY_SOURCE_CONTEXT_KEY, {})[frame.source_id] = events


async def test_process_fires_exactly_once_after_dwell_threshold_crossed() -> None:
    camera_id = uuid4()
    zone = AnalyticsZone(
        camera_id=camera_id,
        name="Full frame",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
    )
    detector = LoiteringDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}
    fired_events: list[DetectionEvent] = []

    for second in range(8):  # 0..7s; threshold crosses at second=5
        frame = _frame(second, sequence=second)
        _set_context_events(context, frame, [_source_event(frame, camera_id, track_id=1)])
        events = await detector.process(frame, context)
        fired_events.extend(events)
        if second < 5:
            assert events == [], f"must not fire before threshold at second={second}"
        elif second == 5:
            assert len(events) == 1, "must fire exactly on the frame threshold is first crossed"
        else:
            assert events == [], f"must not re-fire every subsequent frame at second={second}"

    assert len(fired_events) == 1
    event = fired_events[0]
    assert event.event_type == "loitering_detection.dwell_exceeded"
    assert event.metadata["zone_id"] == str(zone.id)
    assert event.metadata["zone_name"] == "Full frame"
    assert event.metadata["track_id"] == 1
    assert event.metadata["threshold_seconds"] == 5.0
    assert event.metadata["dwell_seconds"] >= 5.0
    assert event.camera_id == camera_id
    assert event.bounding_box == _CENTER_BOX


async def test_process_ignores_detections_outside_the_zone_polygon() -> None:
    camera_id = uuid4()
    zone = AnalyticsZone(
        camera_id=camera_id,
        name="Left half",
        polygon=_LEFT_HALF_ZONE_POLYGON,
        dwell_threshold_seconds=1.0,
    )
    detector = LoiteringDetector(zone_repository=_FakeZoneRepository([zone]))
    outside_box = BoundingBox(x_min=0.6, y_min=0.4, x_max=0.8, y_max=0.6)  # foot point x=0.7
    context: dict = {}

    for second in range(5):
        frame = _frame(second, sequence=second)
        _set_context_events(
            context, frame, [_source_event(frame, camera_id, track_id=1, box=outside_box)]
        )
        events = await detector.process(frame, context)
        assert events == []


async def test_process_resets_dwell_timer_on_zone_exit_and_can_fire_again_on_reentry() -> None:
    camera_id = uuid4()
    zone = AnalyticsZone(
        camera_id=camera_id,
        name="Full frame",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
    )
    detector = LoiteringDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    # Dwell for 3s (below threshold).
    for second in range(3):
        frame = _frame(second, sequence=second)
        _set_context_events(context, frame, [_source_event(frame, camera_id, track_id=1)])
        assert await detector.process(frame, context) == []

    # Track disappears entirely for one frame (left the zone/lost by tracker).
    gap_frame = _frame(3, sequence=3)
    _set_context_events(context, gap_frame, [])
    assert await detector.process(gap_frame, context) == []

    # Re-enters at t=10s. Even though 10s already elapsed since the *original*
    # entry (past the 5s threshold), it must not fire immediately — the timer
    # restarted on re-entry, this is a new dwell period.
    reentry_frame = _frame(10, sequence=4)
    _set_context_events(
        context, reentry_frame, [_source_event(reentry_frame, camera_id, track_id=1)]
    )
    assert await detector.process(reentry_frame, context) == []

    # Still under the new threshold.
    almost_frame = _frame(14, sequence=5)
    _set_context_events(context, almost_frame, [_source_event(almost_frame, camera_id, track_id=1)])
    assert await detector.process(almost_frame, context) == []

    # New dwell period crosses its own threshold -> fires again.
    fires_frame = _frame(15, sequence=6)
    _set_context_events(context, fires_frame, [_source_event(fires_frame, camera_id, track_id=1)])
    events = await detector.process(fires_frame, context)
    assert len(events) == 1


async def test_process_evicts_track_state_when_track_disappears() -> None:
    """Bounded-growth guard (Risks section): state for a track must not
    persist forever once the track is no longer detected at all."""
    camera_id = uuid4()
    zone = AnalyticsZone(
        camera_id=camera_id,
        name="Full frame",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
    )
    detector = LoiteringDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    frame0 = _frame(0, sequence=0)
    _set_context_events(context, frame0, [_source_event(frame0, camera_id, track_id=1)])
    await detector.process(frame0, context)
    assert list(context[_TRACK_STATE_CONTEXT_KEY]["mp4-demo"][zone.id].keys()) == [1]

    frame1 = _frame(1, sequence=1)
    _set_context_events(context, frame1, [])  # track no longer detected at all
    await detector.process(frame1, context)

    assert context[_TRACK_STATE_CONTEXT_KEY]["mp4-demo"] == {}


async def test_process_returns_nothing_when_camera_has_no_zones() -> None:
    camera_id = uuid4()
    detector = LoiteringDetector(zone_repository=_FakeZoneRepository([]))
    frame = _frame(0)
    context: dict = {}
    _set_context_events(context, frame, [_source_event(frame, camera_id, track_id=1)])

    events = await detector.process(frame, context)

    assert events == []


async def test_process_ignores_other_sources_state_in_shared_context() -> None:
    """The single shared `AnalyticsOrchestrator` serves multiple concurrent
    sources (docs/TECHNICAL_DECISIONS.md TD-24/TD-26/TD-27) — dwell state for
    one source must not be affected by another source's frames sharing the
    same `context` dict."""
    camera_id = uuid4()
    zone = AnalyticsZone(
        camera_id=camera_id,
        name="Full frame",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
    )
    detector = LoiteringDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}
    source_a_events: list[DetectionEvent] = []
    source_b_events: list[DetectionEvent] = []

    for second in range(6):  # 0..5s; source-a's dwell crosses 5s threshold at second=5
        frame_a = _frame(second, source_id="source-a", sequence=second)
        _set_context_events(context, frame_a, [_source_event(frame_a, camera_id, track_id=1)])
        source_a_events.extend(await detector.process(frame_a, context))

        # A different source's single frame, always at the same timestamp
        # (t=0), sharing the same `context` dict — must never contribute to
        # or reset "source-a"'s dwell timer, and never itself accumulates
        # dwell time since its own timestamp never advances.
        frame_b = _frame(0, source_id="source-b", sequence=0)
        _set_context_events(context, frame_b, [_source_event(frame_b, camera_id, track_id=1)])
        source_b_events.extend(await detector.process(frame_b, context))

    assert len(source_a_events) == 1
    assert source_a_events[0].metadata["source_id"] == "source-a"
    assert source_b_events == []


async def test_process_skips_detections_without_a_track_id() -> None:
    camera_id = uuid4()
    zone = AnalyticsZone(
        camera_id=camera_id,
        name="Full frame",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=1.0,
    )
    detector = LoiteringDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    for second in range(3):
        frame = _frame(second, sequence=second)
        _set_context_events(context, frame, [_source_event(frame, camera_id, track_id=None)])
        events = await detector.process(frame, context)
        assert events == []
