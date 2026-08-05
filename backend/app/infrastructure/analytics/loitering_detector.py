from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.application.ports.detector_plugin import IDetectorPlugin
from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.infrastructure.analytics.geometry import foot_point, point_in_polygon
from app.infrastructure.analytics.yolo_detector import EVENTS_BY_SOURCE_CONTEXT_KEY

# Namespaced per docs/ARCHITECTURE.md §6.4's guidance ("plugins may store
# their own cross-frame state in it, namespaced by plugin_id if needed").
# Structure: {source_id: {zone_id: {track_id: _DwellState}}} — source_id
# first (TD-26/TD-27's precedent: the single shared AnalyticsOrchestrator
# serves multiple concurrent sources, so an unkeyed dict would let one
# source's dwell state bleed into another's).
_TRACK_STATE_CONTEXT_KEY = "loitering_detector.track_state"

_EVENT_TYPE = "loitering_detection.dwell_exceeded"


@dataclass
class _DwellState:
    entered_at: datetime
    fired: bool


class LoiteringDetector(IDetectorPlugin):
    """Flags a tracked object that dwells inside a configured `AnalyticsZone`
    past its threshold (T-113).

    Reads the current frame's `DetectionEvent`s (with `bounding_box`/
    `metadata["track_id"]`) from `context` under `EVENTS_BY_SOURCE_CONTEXT_KEY`
    — the same same-frame handoff `ColorDetector` already uses (TD-27) —
    rather than re-running detection/tracking. Must therefore run after
    `YoloObjectDetector` in the plugin list (see `container.py`'s ordering
    comment).

    For each of the source camera's zones, tests each tracked detection's
    foot point (`geometry.foot_point`) for containment (`geometry.point_in_polygon`)
    and accumulates dwell time per `(source_id, zone_id, track_id)` in `context`.
    Dwell is measured using `Frame.timestamp`, not wall-clock time at
    processing time (unlike `YoloObjectDetector`/`ColorDetector`'s
    `datetime.now(UTC)` for their own instantaneous, frame-scoped findings) —
    a dwell *period* is fundamentally about elapsed time between frames, and
    wall-clock time at process() call time would be wrong whenever frame
    production isn't real-time (e.g. MP4 playback faster/slower than
    real time). Emits exactly one `DetectionEvent` the first time a track's
    dwell crosses its zone's threshold (a `fired` flag prevents re-emitting
    every subsequent qualifying frame); leaving the zone (or disappearing
    from tracking entirely) resets the timer, so a later re-entry can fire
    again as a new dwell period.
    """

    def __init__(self, zone_repository: IAnalyticsZoneRepository) -> None:
        self._zone_repository = zone_repository

    @property
    def plugin_id(self) -> str:
        return "loitering_detector"

    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        events_by_source: dict[str, list[DetectionEvent]] = context.get(
            EVENTS_BY_SOURCE_CONTEXT_KEY, {}
        )
        source_events = events_by_source.get(frame.source_id, [])
        state_by_source: dict[str, dict[UUID, dict[int, _DwellState]]] = context.setdefault(
            _TRACK_STATE_CONTEXT_KEY, {}
        )
        per_source_state = state_by_source.setdefault(frame.source_id, {})

        if not source_events:
            # Nothing tracked this frame for this source: every previously
            # dwelling track has left/disappeared, so all state resets.
            per_source_state.clear()
            return []

        camera_id = source_events[0].camera_id
        zones = await self._zone_repository.list_by_camera(camera_id)
        if not zones:
            per_source_state.clear()
            return []

        # Evict state for any zone that no longer exists (deleted since a
        # prior frame) so `context` doesn't retain stale zones forever.
        current_zone_ids = {zone.id for zone in zones}
        for stale_zone_id in [zid for zid in per_source_state if zid not in current_zone_ids]:
            del per_source_state[stale_zone_id]

        events: list[DetectionEvent] = []
        for zone in zones:
            events.extend(self._process_zone(frame, zone, source_events, per_source_state))
        return events

    def _process_zone(
        self,
        frame: Frame,
        zone: AnalyticsZone,
        source_events: list[DetectionEvent],
        per_source_state: dict[UUID, dict[int, _DwellState]],
    ) -> list[DetectionEvent]:
        zone_state = per_source_state.setdefault(zone.id, {})
        in_zone_now: dict[int, DetectionEvent] = {}
        for event in source_events:
            track_id = event.metadata.get("track_id")
            if track_id is None or event.bounding_box is None:
                continue
            if point_in_polygon(foot_point(event.bounding_box), zone.polygon):
                in_zone_now[track_id] = event

        events: list[DetectionEvent] = []
        for track_id, source_event in in_zone_now.items():
            dwell_state = zone_state.get(track_id)
            if dwell_state is None:
                zone_state[track_id] = _DwellState(entered_at=frame.timestamp, fired=False)
                continue
            dwell_seconds = (frame.timestamp - dwell_state.entered_at).total_seconds()
            if dwell_seconds >= zone.dwell_threshold_seconds and not dwell_state.fired:
                dwell_state.fired = True
                events.append(self._build_event(frame, zone, track_id, source_event, dwell_seconds))

        # Evict tracks that left the zone (or disappeared entirely, since
        # `in_zone_now` is recomputed fresh from this frame's own events).
        for track_id in [tid for tid in zone_state if tid not in in_zone_now]:
            del zone_state[track_id]

        return events

    def _build_event(
        self,
        frame: Frame,
        zone: AnalyticsZone,
        track_id: int,
        source_event: DetectionEvent,
        dwell_seconds: float,
    ) -> DetectionEvent:
        return DetectionEvent(
            camera_id=source_event.camera_id,
            event_type=_EVENT_TYPE,
            occurred_at=frame.timestamp,
            confidence=1.0,
            bounding_box=source_event.bounding_box,
            metadata={
                "source_id": frame.source_id,
                "frame_sequence": frame.sequence,
                "zone_id": str(zone.id),
                "zone_name": zone.name,
                "track_id": track_id,
                "class_label": source_event.metadata.get("class_label"),
                "dwell_seconds": dwell_seconds,
                "threshold_seconds": zone.dwell_threshold_seconds,
                "source_event_id": str(source_event.id),
            },
        )
