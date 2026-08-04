"""Generate `backend/tests/fixtures/sample.mp4` — the M2 committed frame-source fixture.

This is a **synthetic** clip (a colored shape moving across a plain
background), not real footage: there was no way to source a real video
clip with visible people/vehicles/plates in this environment. It's enough
to prove `IFrameSource`/Stream Worker/reconnect-supervisor mechanics (M2's
own acceptance criteria — frames flow at the right rate, reconnect works),
but it will NOT be usable once M9+ needs real detectable objects/plates —
see docs/TECHNICAL_DECISIONS.md TD-20 for the open item this leaves.

Usage: `uv run python ../scripts/generate_sample_fixture.py` from `backend/`,
or `python scripts/generate_sample_fixture.py` from the repo root.
"""

from pathlib import Path

import cv2
import numpy as np

_WIDTH, _HEIGHT = 320, 240
_FPS = 10.0
_DURATION_SECONDS = 5
_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "sample.mp4"


def generate(output_path: Path = _OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter.fourcc(*"mp4v"), _FPS, (_WIDTH, _HEIGHT)
    )
    total_frames = int(_FPS * _DURATION_SECONDS)
    try:
        for i in range(total_frames):
            frame = np.full((_HEIGHT, _WIDTH, 3), (40, 40, 40), dtype=np.uint8)
            progress = i / max(total_frames - 1, 1)
            center_x = int(30 + progress * (_WIDTH - 60))
            cv2.circle(frame, (center_x, _HEIGHT // 2), 25, (60, 180, 250), thickness=-1)
            cv2.putText(
                frame,
                f"frame {i}",
                (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            writer.write(frame)
    finally:
        writer.release()


if __name__ == "__main__":
    generate()
    print(f"Wrote {_OUTPUT_PATH}")
