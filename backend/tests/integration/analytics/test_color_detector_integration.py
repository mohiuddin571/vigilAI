"""T-100/T-101: `ColorDetector`'s HSV-bucket dominant-color mapping, plus its
context-based handoff from `YoloObjectDetector` (docs/TECHNICAL_DECISIONS.md
TD-27).

Uses synthetic in-memory solid-color crops (numpy arrays), not real camera/
file I/O — the same reasoning `test_yolo_detector_integration.py` already
documents for why this doesn't need `@pytest.mark.hardware`: a small curated
set of known colors is exactly what T-100's Definition of Done asks for.
"""

from datetime import UTC, datetime
from uuid import uuid4

import numpy as np

from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.domain.value_objects.bounding_box import BoundingBox
from app.domain.value_objects.color_label import ColorLabel
from app.infrastructure.analytics.color_detector import ColorDetector
from app.infrastructure.analytics.yolo_detector import EVENTS_BY_SOURCE_CONTEXT_KEY

_FULL_FRAME_BOX = BoundingBox(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)

# (B, G, R) — OpenCV/numpy channel order, matching `Mp4FileFrameSource`'s
# `cv2.VideoCapture`-decoded frames.
_KNOWN_COLOR_CROPS: list[tuple[tuple[int, int, int], ColorLabel]] = [
    ((0, 0, 255), ColorLabel.RED),
    ((0, 165, 255), ColorLabel.ORANGE),
    ((0, 255, 255), ColorLabel.YELLOW),
    ((0, 255, 0), ColorLabel.GREEN),
    ((255, 0, 0), ColorLabel.BLUE),
    ((128, 0, 128), ColorLabel.PURPLE),
    ((0, 0, 0), ColorLabel.BLACK),
    ((255, 255, 255), ColorLabel.WHITE),
    ((128, 128, 128), ColorLabel.GRAY),
    ((19, 69, 139), ColorLabel.BROWN),  # saddlebrown
]


def _solid_color_frame(bgr: tuple[int, int, int], source_id: str = "mp4-demo") -> Frame:
    image = np.full((20, 20, 3), bgr, dtype=np.uint8)
    return Frame(source_id=source_id, sequence=3, timestamp=datetime.now(UTC), image=image)


def _context_with_source_event(
    frame: Frame, bounding_box: BoundingBox = _FULL_FRAME_BOX
) -> tuple[dict, DetectionEvent]:
    source_event = DetectionEvent(
        camera_id=uuid4(),
        event_type="object_detection.car",
        occurred_at=datetime.now(UTC),
        confidence=0.9,
        bounding_box=bounding_box,
        metadata={
            "source_id": frame.source_id,
            "frame_sequence": frame.sequence,
            "class_label": "car",
            "track_id": 5,
        },
    )
    context = {EVENTS_BY_SOURCE_CONTEXT_KEY: {frame.source_id: [source_event]}}
    return context, source_event


async def test_process_labels_known_solid_color_crops() -> None:
    detector = ColorDetector()
    for bgr, expected_label in _KNOWN_COLOR_CROPS:
        frame = _solid_color_frame(bgr)
        context, _ = _context_with_source_event(frame)

        events = await detector.process(frame, context)

        assert len(events) == 1, f"{bgr} -> expected exactly one event"
        assert (
            events[0].metadata["color_label"] == expected_label.value
        ), f"{bgr} expected {expected_label.value}, got {events[0].metadata['color_label']}"
        assert events[0].event_type == f"color_detection.{expected_label.value}"
        assert events[0].confidence == 1.0


async def test_process_correlates_to_source_detection_via_metadata() -> None:
    frame = _solid_color_frame((0, 0, 255))
    context, source_event = _context_with_source_event(frame)
    detector = ColorDetector()

    events = await detector.process(frame, context)

    assert len(events) == 1
    event = events[0]
    assert event.camera_id == source_event.camera_id
    assert event.bounding_box == source_event.bounding_box
    assert event.metadata["source_event_id"] == str(source_event.id)
    assert event.metadata["track_id"] == 5
    assert event.metadata["class_label"] == "car"
    assert event.metadata["frame_sequence"] == frame.sequence
    assert event.metadata["source_id"] == frame.source_id


async def test_process_returns_nothing_when_no_source_detections_in_context() -> None:
    frame = _solid_color_frame((0, 0, 255))
    detector = ColorDetector()

    events = await detector.process(frame, context={})

    assert events == []


async def test_process_skips_source_events_without_a_bounding_box() -> None:
    frame = _solid_color_frame((0, 0, 255))
    source_event = DetectionEvent(
        camera_id=uuid4(),
        event_type="object_detection.car",
        occurred_at=datetime.now(UTC),
        confidence=0.9,
        bounding_box=None,
        metadata={},
    )
    context = {EVENTS_BY_SOURCE_CONTEXT_KEY: {frame.source_id: [source_event]}}
    detector = ColorDetector()

    events = await detector.process(frame, context)

    assert events == []


async def test_process_ignores_other_sources_events_in_shared_context() -> None:
    """The single shared `AnalyticsOrchestrator` serves multiple concurrent
    sources (docs/TECHNICAL_DECISIONS.md TD-24/TD-26) — this frame's source
    must not pick up another source's boxes out of the same `context` dict.
    """
    frame = _solid_color_frame((0, 0, 255), source_id="mp4-demo")
    other_frame = _solid_color_frame((0, 255, 0), source_id="other-source")
    _, other_source_event = _context_with_source_event(other_frame)
    context = {EVENTS_BY_SOURCE_CONTEXT_KEY: {"other-source": [other_source_event]}}
    detector = ColorDetector()

    events = await detector.process(frame, context)

    assert events == []
