from datetime import UTC, datetime
from typing import Any

import cv2
import numpy as np

from app.application.ports.detector_plugin import IDetectorPlugin
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.domain.value_objects.bounding_box import BoundingBox
from app.domain.value_objects.color_label import ColorLabel
from app.infrastructure.analytics.yolo_detector import EVENTS_BY_SOURCE_CONTEXT_KEY

# OpenCV HSV ranges: H in [0, 180), S/V in [0, 256).
_BLACK_VALUE_MAX = 40
_ACHROMATIC_SATURATION_MAX = 40
_WHITE_VALUE_MIN = 200
_BROWN_VALUE_MAX = 150

# Non-overlapping hue buckets covering the full [0, 180) wheel; red wraps
# around both ends since hue is circular.
_HUE_BUCKETS: list[tuple[int, int, ColorLabel]] = [
    (0, 10, ColorLabel.RED),
    (10, 25, ColorLabel.ORANGE),
    (25, 35, ColorLabel.YELLOW),
    (35, 85, ColorLabel.GREEN),
    (85, 130, ColorLabel.BLUE),
    (130, 160, ColorLabel.PURPLE),
    (160, 180, ColorLabel.RED),
]
# Brown is a dark, desaturated shade of orange, not a distinct hue — carved
# out of the orange bucket by value rather than given its own hue range.
_BROWN_HUE_MIN, _BROWN_HUE_MAX = 10, 25


def _classify_pixel_colors(hsv: np.ndarray) -> np.ndarray:
    """Bucket every pixel of an HSV crop into one of `ColorLabel`'s ten members.

    Per-pixel classification (T-100's "HSV-histogram" approach), not a
    single mean/median color — a crop with mixed lighting or shadow still
    votes toward whichever color actually dominates by pixel count.
    """
    hue = hsv[..., 0].astype(np.int32)
    sat = hsv[..., 1].astype(np.int32)
    val = hsv[..., 2].astype(np.int32)

    is_black = val < _BLACK_VALUE_MAX
    is_achromatic = (~is_black) & (sat < _ACHROMATIC_SATURATION_MAX)
    is_white = is_achromatic & (val >= _WHITE_VALUE_MIN)
    is_gray = is_achromatic & ~is_white
    is_chromatic = ~(is_black | is_achromatic)

    labels = np.empty(hue.shape, dtype=object)
    labels[is_black] = ColorLabel.BLACK
    labels[is_white] = ColorLabel.WHITE
    labels[is_gray] = ColorLabel.GRAY

    for low, high, label in _HUE_BUCKETS:
        bucket_mask = is_chromatic & (hue >= low) & (hue < high)
        labels[bucket_mask] = label

    is_brown = (
        is_chromatic & (hue >= _BROWN_HUE_MIN) & (hue < _BROWN_HUE_MAX) & (val < _BROWN_VALUE_MAX)
    )
    labels[is_brown] = ColorLabel.BROWN

    return labels


def _dominant_color(crop: np.ndarray) -> tuple[ColorLabel, float]:
    """Return the majority-vote `ColorLabel` for a crop plus the winning
    label's pixel-count fraction as a confidence score."""
    if crop.ndim == 2:
        # Grayscale crop: no hue information available, classify on
        # brightness alone by treating it as a zero-saturation HSV image.
        zeros = np.zeros_like(crop)
        hsv = np.stack([zeros, zeros, crop], axis=-1)
    else:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    labels = _classify_pixel_colors(hsv).ravel()
    values, counts = np.unique(labels, return_counts=True)
    dominant_index = int(np.argmax(counts))
    confidence = float(counts[dominant_index]) / float(labels.size)
    return values[dominant_index], confidence


def _crop_bounding_box(image: np.ndarray, box: BoundingBox) -> np.ndarray | None:
    height, width = image.shape[:2]
    x_min = min(max(int(box.x_min * width), 0), width)
    x_max = min(max(int(box.x_max * width), x_min + 1), width)
    y_min = min(max(int(box.y_min * height), 0), height)
    y_max = min(max(int(box.y_max * height), y_min + 1), height)
    if x_min >= x_max or y_min >= y_max:
        return None
    return image[y_min:y_max, x_min:x_max]


class ColorDetector(IDetectorPlugin):
    """Dominant-color extraction on M9's detected bounding boxes (T-100, T-101).

    Reads the current frame's `DetectionEvent`s from `context` under
    `EVENTS_BY_SOURCE_CONTEXT_KEY` — written by `YoloObjectDetector` for the
    same frame/source (see that module's docstring and
    docs/ARCHITECTURE.md §6.4 for why `context` carries this one narrow,
    named cross-plugin key). Crops each detection's `bounding_box` out of
    `frame.image`, classifies its dominant color via a per-pixel HSV bucket
    vote, and emits its own new `DetectionEvent` per source detection —
    mirroring every other plugin's pattern (no plugin mutates another
    plugin's event). Correlated back to the source detection via
    `metadata["source_event_id"]`.

    Never re-runs object detection: if no bounding boxes were published for
    this frame/source (analytics disabled for `YoloObjectDetector`, or
    nothing detected), this plugin simply emits nothing.
    """

    @property
    def plugin_id(self) -> str:
        return "color_detector"

    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        events_by_source: dict[str, list[DetectionEvent]] = context.get(
            EVENTS_BY_SOURCE_CONTEXT_KEY, {}
        )
        source_events = events_by_source.get(frame.source_id, [])
        if not source_events:
            return []

        occurred_at = datetime.now(UTC)
        events: list[DetectionEvent] = []
        for source_event in source_events:
            if source_event.bounding_box is None:
                continue
            crop = _crop_bounding_box(frame.image, source_event.bounding_box)
            if crop is None:
                continue
            label, confidence = _dominant_color(crop)
            events.append(
                DetectionEvent(
                    camera_id=source_event.camera_id,
                    event_type=f"color_detection.{label.value}",
                    occurred_at=occurred_at,
                    confidence=confidence,
                    bounding_box=source_event.bounding_box,
                    metadata={
                        "source_id": frame.source_id,
                        "frame_sequence": frame.sequence,
                        "track_id": source_event.metadata.get("track_id"),
                        "class_label": source_event.metadata.get("class_label"),
                        "color_label": label.value,
                        "source_event_id": str(source_event.id),
                    },
                )
            )
        return events
