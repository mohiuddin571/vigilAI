"""T-130: `PlateLocalizer`'s classical-CV boxing accuracy against the
committed plate-visible fixture (docs/TECHNICAL_DECISIONS.md TD-30).

Ground-truth geometry constants below are duplicated from
`scripts/generate_license_plate_fixture.py` (small, deliberate duplication —
same precedent as this codebase's other small private-helper duplications,
TD-25/TD-29) — keep both in sync if either changes.
"""

from pathlib import Path

from app.infrastructure.analytics.plate_localizer import PlateLocalizer
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "license_plate.mp4"

# Mirrors generate_license_plate_fixture.py's geometry exactly.
_WIDTH, _HEIGHT = 640, 480
_VEHICLE_W, _VEHICLE_H = 360, 200
_PLATE_W, _PLATE_H = 160, 40
_VEHICLE_X = _WIDTH // 2 - _VEHICLE_W // 2
_VEHICLE_Y = _HEIGHT // 2 - _VEHICLE_H // 2
_PLATE_X = _VEHICLE_X + (_VEHICLE_W - _PLATE_W) // 2
_PLATE_Y = _VEHICLE_Y + _VEHICLE_H - _PLATE_H - 20

_EXPECTED_BOX_NORMALIZED = (
    _PLATE_X / _WIDTH,
    _PLATE_Y / _HEIGHT,
    (_PLATE_X + _PLATE_W) / _WIDTH,
    (_PLATE_Y + _PLATE_H) / _HEIGHT,
)

# A candidate counts as "correctly boxing" the plate if it overlaps the
# ground-truth region by at least this much — generous enough to tolerate
# the localizer picking either the plate's outer border rect or its inner
# white rect (both are legitimate "found the plate" outcomes), strict enough
# to reject an unrelated/spurious candidate.
_IOU_MATCH_THRESHOLD = 0.5


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax_min, ay_min, ax_max, ay_max = a
    bx_min, by_min, bx_max, by_max = b
    inter_x_min, inter_y_min = max(ax_min, bx_min), max(ay_min, by_min)
    inter_x_max, inter_y_max = min(ax_max, bx_max), min(ay_max, by_max)
    inter_w, inter_h = max(0.0, inter_x_max - inter_x_min), max(0.0, inter_y_max - inter_y_min)
    intersection = inter_w * inter_h
    area_a = (ax_max - ax_min) * (ay_max - ay_min)
    area_b = (bx_max - bx_min) * (by_max - by_min)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


async def _sampled_frames(stride: int = 5) -> list:
    source = Mp4FileFrameSource(file_path=str(_FIXTURE_PATH), source_id="lpr-fixture", loop=False)
    await source.start()
    frames = []
    try:
        i = 0
        async for frame in source.frames():
            if i % stride == 0:
                frames.append(frame)
            i += 1
    finally:
        await source.stop()
    return frames


async def test_locate_boxes_plate_region_in_majority_of_sampled_frames() -> None:
    localizer = PlateLocalizer()
    frames = await _sampled_frames()
    assert len(frames) > 0

    matches = 0
    for frame in frames:
        candidates = localizer.locate(frame.image)
        boxes_normalized = [(b.x_min, b.y_min, b.x_max, b.y_max) for b in candidates]
        if any(
            _iou(box, _EXPECTED_BOX_NORMALIZED) >= _IOU_MATCH_THRESHOLD for box in boxes_normalized
        ):
            matches += 1

    match_rate = matches / len(frames)
    # T-130's Definition of Done, literally: "majority of sampled frames".
    assert match_rate > 0.5, f"only {matches}/{len(frames)} sampled frames boxed the plate"


async def test_locate_returns_bounded_candidate_count() -> None:
    """Sanity check on the `_MAX_CANDIDATES_PER_FRAME` cap (bounds the
    downstream OCR queue's per-frame backlog, T-133) — not itself an AC, but
    guards against a regression that would silently flood the OCR queue."""
    localizer = PlateLocalizer()
    frames = await _sampled_frames(stride=1)
    for frame in frames:
        assert len(localizer.locate(frame.image)) <= 5
