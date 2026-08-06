"""Generate `backend/tests/fixtures/license_plate.mp4` — the M13 plate-visible
test fixture (T-130/T-131/T-132/T-133/T-134, docs/TECHNICAL_DECISIONS.md TD-30).

Synthetic, like `sample.mp4` (see `generate_sample_fixture.py`/TD-20's own
precedent) — no real footage with a legible plate was available in this
environment. Renders a simple vehicle-body rectangle carrying a light,
bordered plate region with OpenCV-rendered text: high-contrast enough for
both the classical-CV localizer (T-130) and EasyOCR (T-131) to have a
realistic chance against it. This fixture's whole purpose is to exercise
those two pipeline stages end-to-end, not to be representative of arbitrary
real-world footage — see TD-30 for the honestly-measured accuracy this
produces.

The scene is fully static (every frame identical) — deliberately, not an
oversight: unlike `sample.mp4`'s moving circle (which exists to prove
frame-rate/throttling mechanics), this fixture's job is legibility and a
predictable, reproducible ground-truth position for T-130's "majority of
sampled frames" boxing-accuracy test, which a static scene makes trivial to
assert against.

Usage: `uv run python ../scripts/generate_license_plate_fixture.py` from
`backend/`, or `python scripts/generate_license_plate_fixture.py` from the
repo root.
"""

from pathlib import Path

import cv2
import numpy as np

_WIDTH, _HEIGHT = 640, 480
_FPS = 10.0
_DURATION_SECONDS = 5
_OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "license_plate.mp4"
)

# Ground-truth plate text — asserted against by
# test_plate_localizer_integration.py / test_license_plate_recognizer_integration.py
# (those tests duplicate the geometry constants below rather than importing
# this script cross-package; keep both in sync if either changes).
PLATE_TEXT = "VGL1234"

_BACKGROUND_COLOR = (150, 150, 150)  # BGR — flat road/background
_VEHICLE_COLOR = (60, 40, 20)  # dark blue-ish body
_PLATE_COLOR = (235, 235, 235)  # near-white
_PLATE_BORDER_COLOR = (10, 10, 10)
_TEXT_COLOR = (10, 10, 10)

_VEHICLE_W, _VEHICLE_H = 360, 200
_PLATE_W, _PLATE_H = 160, 40
_PLATE_BORDER = 3

_VEHICLE_X = _WIDTH // 2 - _VEHICLE_W // 2
_VEHICLE_Y = _HEIGHT // 2 - _VEHICLE_H // 2
_PLATE_X = _VEHICLE_X + (_VEHICLE_W - _PLATE_W) // 2
_PLATE_Y = _VEHICLE_Y + _VEHICLE_H - _PLATE_H - 20


def _render_frame() -> np.ndarray:
    frame = np.full((_HEIGHT, _WIDTH, 3), _BACKGROUND_COLOR, dtype=np.uint8)

    cv2.rectangle(
        frame,
        (_VEHICLE_X, _VEHICLE_Y),
        (_VEHICLE_X + _VEHICLE_W, _VEHICLE_Y + _VEHICLE_H),
        _VEHICLE_COLOR,
        thickness=-1,
    )
    cv2.rectangle(
        frame,
        (_PLATE_X, _PLATE_Y),
        (_PLATE_X + _PLATE_W, _PLATE_Y + _PLATE_H),
        _PLATE_BORDER_COLOR,
        thickness=-1,
    )
    cv2.rectangle(
        frame,
        (_PLATE_X + _PLATE_BORDER, _PLATE_Y + _PLATE_BORDER),
        (_PLATE_X + _PLATE_W - _PLATE_BORDER, _PLATE_Y + _PLATE_H - _PLATE_BORDER),
        _PLATE_COLOR,
        thickness=-1,
    )
    cv2.putText(
        frame,
        PLATE_TEXT,
        (_PLATE_X + 8, _PLATE_Y + _PLATE_H - 11),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        _TEXT_COLOR,
        2,
        cv2.LINE_AA,
    )
    return frame


def generate(output_path: Path = _OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter.fourcc(*"mp4v"), _FPS, (_WIDTH, _HEIGHT)
    )
    total_frames = int(_FPS * _DURATION_SECONDS)
    try:
        frame = _render_frame()
        for _ in range(total_frames):
            writer.write(frame)
    finally:
        writer.release()


if __name__ == "__main__":
    generate()
    print(f"Wrote {_OUTPUT_PATH}")
