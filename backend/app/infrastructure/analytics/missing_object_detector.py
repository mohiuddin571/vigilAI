from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.application.ports.detector_plugin import IDetectorPlugin
from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.domain.value_objects.bounding_box import BoundingBox
from app.infrastructure.analytics.geometry import foot_point, iou, point_in_polygon
from app.infrastructure.analytics.yolo_detector import EVENTS_BY_SOURCE_CONTEXT_KEY

# Namespaced per docs/ARCHITECTURE.md §6.4's guidance ("the baseline reference
# for missing-object detection" is named there as the canonical example of
# context cross-frame state) — same source-first keying as LoiteringDetector's
# _TRACK_STATE_CONTEXT_KEY (TD-26/TD-27/TD-28's precedent against one
# source's state bleeding into another's via the single shared
# AnalyticsOrchestrator). Structure: {source_id: {zone_id: {track_id: _TrackedBaseline}}}.
# T-120's "baseline stored and retrievable" DoD is satisfied by this key being
# stable/importable and directly inspectable in context, the same way T-113's
# dwell state already is.
BASELINE_CONTEXT_KEY = "missing_object_detector.baseline"

_EVENT_TYPE = "missing_object_detection.object_missing"

# Minimum IoU (against a baseline entry's last-known bounding box) for an
# unmatched in-zone detection to be accepted as that same object reappearing
# under a new track_id, rather than treated as a distinct object.
_REID_IOU_THRESHOLD = 0.3


@dataclass
class _TrackedBaseline:
    """One baseline-registered track's reference state within a zone.

    `bounding_box` is the track's last-known in-zone position — updated
    whenever it's observed present, so a fired event reports where the object
    was last seen rather than its position at baseline-capture time only.
    """

    class_label: str | None
    bounding_box: BoundingBox | None
    absent_since: datetime | None = None
    fired: bool = False


def _derive_camera_id(source_id: str) -> UUID:
    """Duplicated from `yolo_detector._derive_camera_id` rather than imported
    across modules (both are small, private, module-level helpers — see
    docs/TECHNICAL_DECISIONS.md TD-25's precedent for why a leading-underscore
    function is duplicated here instead of imported cross-module).

    Real onboarded cameras use their own `Camera.id` as `source_id`; non-UUID
    sources (e.g. the `"mp4-demo"` fixture) fall back to a deterministic
    `uuid5` derivation, so repeated runs of the same demo source still
    correlate to one id.
    """
    try:
        return UUID(source_id)
    except ValueError:
        return uuid5(NAMESPACE_DNS, source_id)


class MissingObjectDetector(IDetectorPlugin):
    """Flags a tracked object that was present in a zone's baseline reference
    but has since been absent from that zone past its configured threshold
    (T-120, T-121, T-122).

    Reads the current frame's `DetectionEvent`s (with `bounding_box`/
    `metadata["track_id"]`) from `context` under `EVENTS_BY_SOURCE_CONTEXT_KEY`
    — the same same-frame handoff `ColorDetector`/`LoiteringDetector` already
    use (TD-27/TD-28) — rather than re-running detection. Must therefore run
    after `YoloObjectDetector` in the plugin list (see `container.py`'s
    ordering comment). Unlike those two plugins, this one does *not* skip
    processing when a frame has zero detections — an empty frame is exactly
    what "the object is gone" looks like, so `camera_id` is derived directly
    from `frame.source_id` (`_derive_camera_id`) rather than from a
    detection event.

    Only zones with `AnalyticsZone.missing_object_threshold_seconds` set
    participate — this is opt-in per zone, unlike `LoiteringDetector`'s
    always-on `dwell_threshold_seconds` (docs/TECHNICAL_DECISIONS.md TD-29).

    **Baseline capture (T-120)**: for each `(source_id, zone_id)`, the first
    frame that has at least one in-zone tracked detection captures every
    track in-zone at that exact frame as the permanent baseline set, stored
    in `context[BASELINE_CONTEXT_KEY]`. The baseline is captured once and
    never grows afterward — a track that enters the zone for the first time
    on a later frame is not added. This is a deliberate choice, not an
    oversight: a continuously-growing baseline would eventually flag *every*
    transient object that ever passed through the zone (e.g. a person
    walking through and leaving) as "missing," which defeats the purpose of
    a baseline/reference-view detector. The real limitation this trades away
    is documented in TD-29: an object placed in the zone *after* the first
    baseline-eligible frame is never itself baselined.

    **Absence timer (T-121)**: each frame, a baseline track_id present
    in-zone resets its absence timer (and re-arms `fired`, so a later
    disappearance can fire again); an absent one accumulates elapsed time
    (via `Frame.timestamp`, not wall-clock time — TD-28's same reasoning
    applies: elapsed time between frames, not time at process()-call time)
    and fires exactly once when it crosses the zone's threshold.

    **Occlusion guard (T-122)**: falls directly out of the absence-timer
    design above — no separate mechanism. A brief occlusion (detection lost,
    then regained under the same track_id before the threshold) resets
    `absent_since` before it ever crosses the threshold, so no event fires.

    **Track re-identification**: a baseline track_id that goes missing is
    also matched, each frame, against any *unclaimed* in-zone detection of
    the same class whose bounding box overlaps (IoU) its last-known position
    above `_REID_IOU_THRESHOLD`. If matched, the baseline entry is re-keyed
    to the new track_id and treated as present (timer reset) instead of
    absent. This closes a real false-positive gap: a tracker (ByteTrack)
    relabeling a stationary object after a brief detection gap — which can
    happen around zone edits, since deleting and recreating a zone forces a
    fresh baseline capture on the very next in-zone frame — would otherwise
    be indistinguishable from the object actually having been removed, and
    would eventually fire once the old track_id's "absence" crossed the
    threshold even though the object never moved.
    """

    def __init__(self, zone_repository: IAnalyticsZoneRepository) -> None:
        self._zone_repository = zone_repository

    @property
    def plugin_id(self) -> str:
        return "missing_object_detector"

    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        events_by_source: dict[str, list[DetectionEvent]] = context.get(
            EVENTS_BY_SOURCE_CONTEXT_KEY, {}
        )
        source_events = events_by_source.get(frame.source_id, [])
        baseline_by_source: dict[str, dict[UUID, dict[int, _TrackedBaseline]]] = context.setdefault(
            BASELINE_CONTEXT_KEY, {}
        )
        per_source_baseline = baseline_by_source.setdefault(frame.source_id, {})

        camera_id = _derive_camera_id(frame.source_id)
        zones = await self._zone_repository.list_by_camera(camera_id)
        monitored_zones = [z for z in zones if z.missing_object_threshold_seconds is not None]
        if not monitored_zones:
            per_source_baseline.clear()
            return []

        # Evict state for any zone that's no longer monitored (deleted, or
        # its threshold was cleared) since a prior frame, so `context`
        # doesn't retain stale zones forever.
        current_zone_ids = {zone.id for zone in monitored_zones}
        for stale_zone_id in [zid for zid in per_source_baseline if zid not in current_zone_ids]:
            del per_source_baseline[stale_zone_id]

        events: list[DetectionEvent] = []
        for zone in monitored_zones:
            threshold_seconds = zone.missing_object_threshold_seconds
            assert threshold_seconds is not None  # guaranteed by monitored_zones filter above
            events.extend(
                self._process_zone(
                    frame, zone, threshold_seconds, camera_id, source_events, per_source_baseline
                )
            )
        return events

    def _process_zone(
        self,
        frame: Frame,
        zone: AnalyticsZone,
        threshold_seconds: float,
        camera_id: UUID,
        source_events: list[DetectionEvent],
        per_source_baseline: dict[UUID, dict[int, _TrackedBaseline]],
    ) -> list[DetectionEvent]:
        in_zone_now: dict[int, DetectionEvent] = {}
        for event in source_events:
            track_id = event.metadata.get("track_id")
            if track_id is None or event.bounding_box is None:
                continue
            if point_in_polygon(foot_point(event.bounding_box), zone.polygon):
                in_zone_now[track_id] = event

        baseline = per_source_baseline.get(zone.id)
        if baseline is None:
            if not in_zone_now:
                return []
            per_source_baseline[zone.id] = {
                track_id: _TrackedBaseline(
                    class_label=event.metadata.get("class_label"),
                    bounding_box=event.bounding_box,
                )
                for track_id, event in in_zone_now.items()
            }
            return []

        unclaimed_events = dict(in_zone_now)
        resolved: dict[int, DetectionEvent | None] = {}
        for track_id in baseline:
            resolved[track_id] = unclaimed_events.pop(track_id, None)

        # Re-identify baseline tracks whose track_id didn't match directly —
        # a tracker relabel, not necessarily a real absence (see class
        # docstring's "Track re-identification" section).
        for track_id, resolved_event in resolved.items():
            if resolved_event is not None:
                continue
            entry = baseline[track_id]
            if entry.bounding_box is None:
                continue
            best_candidate_id: int | None = None
            best_score = _REID_IOU_THRESHOLD
            for candidate_id, candidate_event in unclaimed_events.items():
                if candidate_event.metadata.get("class_label") != entry.class_label:
                    continue
                if candidate_event.bounding_box is None:
                    continue
                score = iou(entry.bounding_box, candidate_event.bounding_box)
                if score > best_score:
                    best_score = score
                    best_candidate_id = candidate_id
            if best_candidate_id is not None:
                resolved[track_id] = unclaimed_events.pop(best_candidate_id)

        events: list[DetectionEvent] = []
        rekeyed_baseline: dict[int, _TrackedBaseline] = {}
        for track_id, entry in baseline.items():
            source_event = resolved[track_id]
            if source_event is not None:
                entry.bounding_box = source_event.bounding_box
                entry.absent_since = None
                entry.fired = False
                rekeyed_baseline[source_event.metadata["track_id"]] = entry
                continue
            if entry.absent_since is None:
                entry.absent_since = frame.timestamp
            else:
                absence_seconds = (frame.timestamp - entry.absent_since).total_seconds()
                if absence_seconds >= threshold_seconds and not entry.fired:
                    entry.fired = True
                    events.append(
                        self._build_event(
                            frame,
                            zone,
                            camera_id,
                            track_id,
                            entry,
                            absence_seconds,
                            threshold_seconds,
                        )
                    )
            rekeyed_baseline[track_id] = entry
        per_source_baseline[zone.id] = rekeyed_baseline
        return events

    def _build_event(
        self,
        frame: Frame,
        zone: AnalyticsZone,
        camera_id: UUID,
        track_id: int,
        entry: _TrackedBaseline,
        absence_seconds: float,
        threshold_seconds: float,
    ) -> DetectionEvent:
        return DetectionEvent(
            camera_id=camera_id,
            event_type=_EVENT_TYPE,
            occurred_at=frame.timestamp,
            confidence=1.0,
            bounding_box=entry.bounding_box,
            metadata={
                "source_id": frame.source_id,
                "frame_sequence": frame.sequence,
                "zone_id": str(zone.id),
                "zone_name": zone.name,
                "track_id": track_id,
                "class_label": entry.class_label,
                "absence_seconds": absence_seconds,
                "threshold_seconds": threshold_seconds,
            },
        )
