"""Classical CV license-plate region localizer (T-130).

docs/TECHNICAL_DECISIONS.md TD-30: no pretrained YOLO license-plate model is
reachable through Ultralytics' standard `YOLO("name.pt")` auto-download path
(that only covers Ultralytics' own release assets — a third-party plate
model would mean loading an unverified `.pt` pickle from an arbitrary host,
which this repo already declines to do unprompted, TD-20's precedent).
`PlateLocalizer` is the classical-CV fallback `docs/IMPLEMENTATION_PLAN.md`
§M13 names as the alternative: grayscale -> bilateral filter -> Canny edges
-> contours -> filter by rectangular aspect ratio/size, a standard ANPR
candidate-region technique requiring no new ML dependency.

Runs over the *full* frame, independently of `YoloObjectDetector`'s
same-frame `context` (TD-30) — not gated behind vehicle-class boxes. Gating
on YOLO's vehicle detections would produce zero candidates against this
milestone's own synthetic test fixture (YOLO doesn't recognize synthetic
shapes as vehicles, same limitation TD-20/TD-25 already document), so this
localizer is deliberately self-contained.
"""

import cv2
import numpy as np

from app.domain.value_objects.bounding_box import BoundingBox

# Real plates commonly range ~2:1 (US) to ~5.5:1 (some EU formats); kept
# generous to match this milestone's own rendered fixture without overfitting
# to one exact ratio.
_MIN_ASPECT_RATIO = 1.5
_MAX_ASPECT_RATIO = 6.5

# Candidate area, as a fraction of the full frame's area — bounds out both
# single-pixel noise contours and implausibly large "plates" (e.g. an entire
# vehicle body misread as one rectangle).
_MIN_AREA_FRACTION = 0.0005
_MAX_AREA_FRACTION = 0.2

# Canny edge-detection thresholds (a conventional ~1:3 low:high ratio).
_CANNY_LOW = 50
_CANNY_HIGH = 150

# `approxPolyDP` epsilon, as a fraction of the contour's perimeter — allows a
# little noise while still favoring near-rectangular shapes.
_POLY_APPROX_EPSILON_FRACTION = 0.02
_MIN_POLYGON_VERTICES = 4
_MAX_POLYGON_VERTICES = 8

# Caps how many candidates one frame can hand off to OCR, in descending
# contour-area order — keeps the downstream OCR queue's per-frame backlog
# bounded regardless of how cluttered a scene is.
_MAX_CANDIDATES_PER_FRAME = 5


class PlateLocalizer:
    """Finds candidate license-plate regions in a frame via classical CV.

    Not an `IDetectorPlugin` itself — composed by `LicensePlateRecognizer`
    (T-132), which owns the `DetectionEvent`/`context` boundary. `locate()`
    is synchronous and CPU-bound; the caller is responsible for keeping it
    off the asyncio event loop if needed (`LicensePlateRecognizer` wraps it
    in `asyncio.to_thread`, since full-frame contour work is heavier than a
    single `cv2.cvtColor` call like `ColorDetector`'s).
    """

    def locate(self, image: np.ndarray) -> list[BoundingBox]:
        height, width = image.shape[:2]
        if height == 0 or width == 0:
            return []
        frame_area = float(height * width)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        # Bilateral filter smooths flat regions (paint, background) while
        # preserving the sharp edges Canny needs — a plain Gaussian blur
        # would soften those edges indiscriminately along with the noise.
        smoothed = cv2.bilateralFilter(gray, d=11, sigmaColor=17, sigmaSpace=17)
        edges = cv2.Canny(smoothed, _CANNY_LOW, _CANNY_HIGH)

        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        candidates: list[tuple[float, BoundingBox]] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not (_MIN_AREA_FRACTION <= area / frame_area <= _MAX_AREA_FRACTION):
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            approx = cv2.approxPolyDP(contour, _POLY_APPROX_EPSILON_FRACTION * perimeter, True)
            if not (_MIN_POLYGON_VERTICES <= len(approx) <= _MAX_POLYGON_VERTICES):
                continue

            x, y, w, h = cv2.boundingRect(contour)
            if w == 0 or h == 0 or not (_MIN_ASPECT_RATIO <= w / h <= _MAX_ASPECT_RATIO):
                continue

            box = BoundingBox(
                x_min=x / width,
                y_min=y / height,
                x_max=min((x + w) / width, 1.0),
                y_max=min((y + h) / height, 1.0),
            )
            candidates.append((area, box))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [box for _, box in candidates[:_MAX_CANDIDATES_PER_FRAME]]
