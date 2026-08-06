"""T-120/T-121/T-122: `MissingObjectDetector`'s baseline capture, absence
timer, and occlusion false-positive guard, plus its context-based handoff
from `YoloObjectDetector` (docs/TECHNICAL_DECISIONS.md TD-27/TD-29).

Uses synthetic track data (constructed `Frame`/`DetectionEvent`/`AnalyticsZone`
fixtures), not real footage — the same reasoning `test_loitering_detector_integration.py`
already documents: `sample.mp4` is a synthetic clip with no real missing-object
scenario in it (docs/TECHNICAL_DECISIONS.md TD-20/TD-25), and this milestone's
own acceptance criteria ("event fires after the configured threshold and not
before", T-122's "crafted test... or unit test using synthetic detection
sequences") are exactly what synthetic, precisely-timed frames let this test
assert deterministically.

A single `context` dict is reused across every `process()` call within a test
(not rebuilt each iteration) — this mirrors how `AnalyticsOrchestrator` reuses
one `self._context` for the lifetime of a pipeline run, which is what lets
`MissingObjectDetector`'s cross-frame baseline/absence state actually
accumulate.

`camera_id` in every fixture below is derived from `source_id` via the same
`_derive_camera_id` the detector itself uses (TD-29 decision 3) — unlike
`LoiteringDetector`, which reads `camera_id` off the current frame's own
detection events, `MissingObjectDetector` must still resolve a `camera_id`
on frames with zero detections (that's exactly when an object is "missing"),
so it derives one from `frame.source_id` directly. A test using an unrelated
random `camera_id` would make `_FakeZoneRepository.list_by_camera` never
match the zone at all.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import numpy as np

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.domain.value_objects.bounding_box import BoundingBox
from app.infrastructure.analytics.missing_object_detector import (
    BASELINE_CONTEXT_KEY,
    MissingObjectDetector,
    _derive_camera_id,
)
from app.infrastructure.analytics.yolo_detector import EVENTS_BY_SOURCE_CONTEXT_KEY

_BLANK_IMAGE = np.zeros((20, 20, 3), dtype=np.uint8)
_BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)
_FULL_FRAME_ZONE_POLYGON = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
_LEFT_HALF_ZONE_POLYGON = [(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)]
_CENTER_BOX = BoundingBox(x_min=0.4, y_min=0.4, x_max=0.6, y_max=0.6)
_SOURCE_ID = "mp4-demo"
_CAMERA_ID = _derive_camera_id(_SOURCE_ID)


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


def _frame(second: float, source_id: str, sequence: int) -> Frame:
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
        event_type="object_detection.backpack",
        occurred_at=frame.timestamp,
        confidence=0.9,
        bounding_box=box,
        metadata={
            "source_id": frame.source_id,
            "frame_sequence": frame.sequence,
            "class_label": "backpack",
            "track_id": track_id,
        },
    )


def _set_context_events(context: dict, frame: Frame, events: list[DetectionEvent]) -> None:
    context.setdefault(EVENTS_BY_SOURCE_CONTEXT_KEY, {})[frame.source_id] = events


async def test_baseline_is_captured_and_retrievable_on_first_in_zone_detection() -> None:
    """T-120: "Baseline stored and retrievable"."""
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Storage room",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=10.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    frame0 = _frame(0, _SOURCE_ID, sequence=0)
    _set_context_events(context, frame0, [_source_event(frame0, _CAMERA_ID, track_id=1)])
    events = await detector.process(frame0, context)

    assert events == []  # capturing baseline never itself fires an event
    baseline = context[BASELINE_CONTEXT_KEY][_SOURCE_ID][zone.id]
    assert list(baseline.keys()) == [1]
    assert baseline[1].class_label == "backpack"
    assert baseline[1].bounding_box == _CENTER_BOX
    assert baseline[1].absent_since is None
    assert baseline[1].fired is False


async def test_process_ignores_zones_without_a_missing_object_threshold() -> None:
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Storage room",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        # missing_object_threshold_seconds left unset (opt-in per zone)
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    for second in range(20):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        events_this_frame = [_source_event(frame, _CAMERA_ID, track_id=1)] if second == 0 else []
        _set_context_events(context, frame, events_this_frame)
        assert await detector.process(frame, context) == []
    assert BASELINE_CONTEXT_KEY not in context or context[BASELINE_CONTEXT_KEY][_SOURCE_ID] == {}


async def test_process_fires_exactly_once_after_absence_threshold_crossed() -> None:
    """AC #1: "object present at baseline capture, later removed from frame,
    event fires after the configured threshold and not before."""
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Storage room",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=5.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}
    fired_events: list[DetectionEvent] = []

    # t=0: baseline capture (object present).
    frame0 = _frame(0, _SOURCE_ID, sequence=0)
    _set_context_events(context, frame0, [_source_event(frame0, _CAMERA_ID, track_id=1)])
    assert await detector.process(frame0, context) == []

    # t=1..8: object removed from frame entirely (zero detections at all) —
    # absence timer starts at t=1 (first frame it's missing), crosses the 5s
    # threshold at t=6.
    for second in range(1, 9):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        _set_context_events(context, frame, [])
        events = await detector.process(frame, context)
        fired_events.extend(events)
        if second < 6:
            assert events == [], f"must not fire before threshold at second={second}"
        elif second == 6:
            assert len(events) == 1, "must fire exactly on the frame threshold is first crossed"
        else:
            assert events == [], f"must not re-fire every subsequent frame at second={second}"

    assert len(fired_events) == 1
    event = fired_events[0]
    assert event.event_type == "missing_object_detection.object_missing"
    assert event.metadata["zone_id"] == str(zone.id)
    assert event.metadata["zone_name"] == "Storage room"
    assert event.metadata["track_id"] == 1
    assert event.metadata["class_label"] == "backpack"
    assert event.metadata["threshold_seconds"] == 5.0
    assert event.metadata["absence_seconds"] >= 5.0
    assert event.camera_id == _CAMERA_ID
    assert event.bounding_box == _CENTER_BOX


async def test_process_ignores_detections_outside_the_zone_polygon() -> None:
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Left half",
        polygon=_LEFT_HALF_ZONE_POLYGON,
        dwell_threshold_seconds=1.0,
        missing_object_threshold_seconds=1.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    outside_box = BoundingBox(x_min=0.6, y_min=0.4, x_max=0.8, y_max=0.6)  # foot point x=0.7
    context: dict = {}

    for second in range(5):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        _set_context_events(
            context, frame, [_source_event(frame, _CAMERA_ID, track_id=1, box=outside_box)]
        )
        events = await detector.process(frame, context)
        assert events == []


async def test_brief_occlusion_under_threshold_does_not_fire() -> None:
    """T-122: "brief occlusion (a person walking in front of the object for
    under the threshold) does not fire an event"."""
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Storage room",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=10.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    # t=0: baseline capture.
    frame0 = _frame(0, _SOURCE_ID, sequence=0)
    _set_context_events(context, frame0, [_source_event(frame0, _CAMERA_ID, track_id=1)])
    assert await detector.process(frame0, context) == []

    # t=1..3: occluded (a person walks in front — no detection for the
    # tracked object at all, 3s < the 10s threshold).
    for second in (1, 2, 3):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        _set_context_events(context, frame, [])
        assert await detector.process(frame, context) == []

    # t=4: object reappears under the same track id (ByteTrack persisted
    # through the brief occlusion) — absence timer resets.
    reappear_frame = _frame(4, _SOURCE_ID, sequence=4)
    _set_context_events(
        context, reappear_frame, [_source_event(reappear_frame, _CAMERA_ID, track_id=1)]
    )
    assert await detector.process(reappear_frame, context) == []

    # t=5..20: object stays present — must never fire, even though 20s have
    # elapsed since baseline (well past the 10s threshold), since it never
    # actually stayed absent that long.
    for second in range(5, 21):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        _set_context_events(context, frame, [_source_event(frame, _CAMERA_ID, track_id=1)])
        assert await detector.process(frame, context) == []


async def test_reappearance_resets_fired_flag_allowing_a_later_event() -> None:
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Storage room",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=3.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    frame0 = _frame(0, _SOURCE_ID, sequence=0)
    _set_context_events(context, frame0, [_source_event(frame0, _CAMERA_ID, track_id=1)])
    await detector.process(frame0, context)

    # First absence crosses the 3s threshold at t=3 -> fires once.
    fired_once = []
    for second in range(1, 5):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        _set_context_events(context, frame, [])
        fired_once.extend(await detector.process(frame, context))
    assert len(fired_once) == 1

    # Object comes back at t=10.
    back_frame = _frame(10, _SOURCE_ID, sequence=5)
    _set_context_events(context, back_frame, [_source_event(back_frame, _CAMERA_ID, track_id=1)])
    assert await detector.process(back_frame, context) == []

    # It goes missing again and crosses the threshold a second time -> fires again.
    fired_twice = []
    for second in range(11, 15):
        frame = _frame(second, _SOURCE_ID, sequence=second + 10)
        _set_context_events(context, frame, [])
        fired_twice.extend(await detector.process(frame, context))
    assert len(fired_twice) == 1


async def test_process_returns_nothing_when_camera_has_no_zones() -> None:
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([]))
    frame = _frame(0, _SOURCE_ID, sequence=0)
    context: dict = {}
    _set_context_events(context, frame, [_source_event(frame, _CAMERA_ID, track_id=1)])

    events = await detector.process(frame, context)

    assert events == []


async def test_process_ignores_other_sources_state_in_shared_context() -> None:
    """The single shared `AnalyticsOrchestrator` serves multiple concurrent
    sources (docs/TECHNICAL_DECISIONS.md TD-24/TD-26/TD-27/TD-29) — absence
    state for one source must not be affected by another source's frames
    sharing the same `context` dict. Each source has its own derived
    `camera_id` (TD-29 decision 3) and therefore its own zone."""
    camera_id_a = _derive_camera_id("source-a")
    camera_id_b = _derive_camera_id("source-b")
    zone_a = AnalyticsZone(
        camera_id=camera_id_a,
        name="Storage room A",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=5.0,
    )
    zone_b = AnalyticsZone(
        camera_id=camera_id_b,
        name="Storage room B",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=5.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone_a, zone_b]))
    context: dict = {}
    source_a_events: list[DetectionEvent] = []
    source_b_events: list[DetectionEvent] = []

    # source-a: baseline at t=0, then removed — crosses its 5s threshold at t=6.
    frame_a0 = _frame(0, "source-a", sequence=0)
    _set_context_events(context, frame_a0, [_source_event(frame_a0, camera_id_a, track_id=1)])
    await detector.process(frame_a0, context)

    for second in range(1, 7):
        frame_a = _frame(second, "source-a", sequence=second)
        _set_context_events(context, frame_a, [])
        source_a_events.extend(await detector.process(frame_a, context))

        # source-b: object always present, always at the same timestamp
        # (t=0) — must never fire, and must not disturb source-a's state.
        frame_b = _frame(0, "source-b", sequence=0)
        _set_context_events(context, frame_b, [_source_event(frame_b, camera_id_b, track_id=1)])
        source_b_events.extend(await detector.process(frame_b, context))

    assert len(source_a_events) == 1
    assert source_a_events[0].metadata["source_id"] == "source-a"
    assert source_b_events == []


async def test_track_id_relabel_does_not_fire_when_position_still_overlaps() -> None:
    """A tracker (ByteTrack) can relabel a stationary object's track_id after
    a brief detection gap without the object ever having moved — e.g. right
    around a zone being deleted and recreated, which forces a fresh baseline
    capture on the very next in-zone frame. The re-identification fallback
    (IoU + class match against the baseline entry's last-known box) must
    treat this as the same object reappearing, not as it going missing."""
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Storage room",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=5.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    # t=0: baseline capture under track_id=1.
    frame0 = _frame(0, _SOURCE_ID, sequence=0)
    _set_context_events(context, frame0, [_source_event(frame0, _CAMERA_ID, track_id=1)])
    assert await detector.process(frame0, context) == []

    # t=1..20: the object never moves (same box, same class) but the
    # tracker relabels it to track_id=2 from t=1 onward — well past the 5s
    # threshold, this must never fire.
    for second in range(1, 21):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        _set_context_events(context, frame, [_source_event(frame, _CAMERA_ID, track_id=2)])
        assert await detector.process(frame, context) == []

    baseline = context[BASELINE_CONTEXT_KEY][_SOURCE_ID][zone.id]
    assert list(baseline.keys()) == [2]  # re-keyed from 1 to 2
    assert baseline[2].absent_since is None


async def test_track_id_relabel_to_non_overlapping_position_still_fires() -> None:
    """Re-identification must not paper over a genuine absence: if the new
    track_id's box doesn't overlap the baseline's last-known position, it's
    a different object, not a relabel, and the original must still fire."""
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Storage room",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=5.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}
    far_box = BoundingBox(x_min=0.0, y_min=0.0, x_max=0.1, y_max=0.1)

    frame0 = _frame(0, _SOURCE_ID, sequence=0)
    _set_context_events(context, frame0, [_source_event(frame0, _CAMERA_ID, track_id=1)])
    assert await detector.process(frame0, context) == []

    fired_events: list[DetectionEvent] = []
    for second in range(1, 9):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        _set_context_events(
            context, frame, [_source_event(frame, _CAMERA_ID, track_id=2, box=far_box)]
        )
        fired_events.extend(await detector.process(frame, context))

    assert len(fired_events) == 1
    assert fired_events[0].metadata["track_id"] == 1


async def test_process_skips_detections_without_a_track_id() -> None:
    zone = AnalyticsZone(
        camera_id=_CAMERA_ID,
        name="Storage room",
        polygon=_FULL_FRAME_ZONE_POLYGON,
        dwell_threshold_seconds=1.0,
        missing_object_threshold_seconds=1.0,
    )
    detector = MissingObjectDetector(zone_repository=_FakeZoneRepository([zone]))
    context: dict = {}

    for second in range(3):
        frame = _frame(second, _SOURCE_ID, sequence=second)
        _set_context_events(context, frame, [_source_event(frame, _CAMERA_ID, track_id=None)])
        events = await detector.process(frame, context)
        assert events == []
