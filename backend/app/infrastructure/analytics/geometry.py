"""Shared zone/region-containment primitives for zone-aware detector plugins.

Promoted out of `loitering_detector.py` (M11/T-113) so `missing_object_detector.py`
(M12/T-121) can reuse the same containment check without reimplementing it —
this was flagged as the natural next step in docs/TECHNICAL_DECISIONS.md TD-28's
Future Enhancement note ("Consider promoting the point-in-polygon helper to a
small shared geometry utility if a future milestone... needs the same
zone/region-containment primitive").
"""

from app.domain.value_objects.bounding_box import BoundingBox


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Standard ray-casting (Jordan curve) point-in-polygon test.

    Pure Python, no new dependency (AGENTS.md § Dependency Rules) — `polygon`
    and `point` are both in the same normalized `[0, 1]` space `BoundingBox`
    already uses, so no coordinate conversion is needed here.
    """
    x, y = point
    inside = False
    x1, y1 = polygon[-1]
    for x2, y2 in polygon:
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
        x1, y1 = x2, y2
    return inside


def foot_point(box: BoundingBox) -> tuple[float, float]:
    """The bounding box's bottom-center point — where a tracked object actually
    stands, unlike the box's visual center (which sits on a person's torso,
    not their feet). This is the point tested for zone containment."""
    return ((box.x_min + box.x_max) / 2, box.y_max)


def iou(box_a: BoundingBox, box_b: BoundingBox) -> float:
    """Intersection-over-union of two normalized `[0, 1]` bounding boxes.

    Used to re-identify a tracked object across a track_id change (e.g. a
    tracker relabeling it after a brief detection gap) by matching its last-
    known position rather than its (now-stale) track_id.
    """
    x_min = max(box_a.x_min, box_b.x_min)
    y_min = max(box_a.y_min, box_b.y_min)
    x_max = min(box_a.x_max, box_b.x_max)
    y_max = min(box_a.y_max, box_b.y_max)
    if x_max <= x_min or y_max <= y_min:
        return 0.0
    intersection = (x_max - x_min) * (y_max - y_min)
    union = box_a.width * box_a.height + box_b.width * box_b.height - intersection
    return intersection / union if union > 0 else 0.0
