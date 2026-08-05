"""T-091/T-110: `YoloObjectDetector.process()`'s detection+tracking mapping
shape, against a real decoded frame.

Uses a real `Frame` decoded from the committed `backend/tests/fixtures/sample.mp4`
(the AGENTS.md "against the local MP4 fixture" integration-test convention),
but injects a fake/stub Ultralytics-shaped model (now shaped like `.track()`,
including per-box track ids — T-110, docs/TECHNICAL_DECISIONS.md TD-26)
rather than loading real weights and running real inference.

This is deliberate, not a shortcut: `sample.mp4` is a synthetic clip (a
colored circle moving across a plain background — docs/TECHNICAL_DECISIONS.md
TD-20's documented, still-current limitation), which contains no real COCO
object. Real inference against it would correctly return an empty detection
list, which proves nothing about the mapping logic this milestone actually
wrote (pixel/normalized box handling, `DetectionEvent`/`BoundingBox`
construction, class-label attachment, track-id surfacing). The manual,
real-inference spot check required by T-091's Acceptance Criteria was instead
performed against the live physical camera feed and is recorded in
docs/TECHNICAL_DECISIONS.md TD-25 — see that entry for what was visually
confirmed. T-110's own acceptance bar ("same object retains one ID across
consecutive frames") is verified below with the stubbed model returning the
same track id across two consecutive `process()` calls, following this same
established stub-model pattern.
"""

from pathlib import Path
from uuid import UUID

from app.infrastructure.analytics.yolo_detector import YoloObjectDetector
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"


class _StubTensor:
    def __init__(self, values: list) -> None:
        self._values = values

    def tolist(self) -> list:
        return self._values


class _StubBoxes:
    def __init__(self, xyxyn: list, cls: list, conf: list, id: list | None = None) -> None:
        self.xyxyn = _StubTensor(xyxyn)
        self.cls = _StubTensor(cls)
        self.conf = _StubTensor(conf)
        self.id = _StubTensor(id) if id is not None else None


class _StubResult:
    def __init__(self, names: dict, boxes: _StubBoxes | None) -> None:
        self.names = names
        self.boxes = boxes


class _StubModel:
    """A fake shaped like `ultralytics.YOLO`'s `.track()` inference interface.

    `results_sequence` holds one entry per expected `.track()` call (popped
    in order), so a test can drive several consecutive `process()` calls with
    different stub results — needed to simulate consecutive frames for the
    track-id-stability test below.
    """

    def __init__(self, results_sequence: list[list[_StubResult]]) -> None:
        self._results_sequence = list(results_sequence)
        self.calls: list[dict] = []

    def track(self, source: object, **kwargs: object) -> list[_StubResult]:
        self.calls.append({"source": source, **kwargs})
        return self._results_sequence.pop(0)


async def _one_real_frame() -> object:
    source = Mp4FileFrameSource(file_path=str(_FIXTURE_PATH), source_id="mp4-fixture", loop=False)
    await source.start()
    try:
        async for frame in source.frames():
            return frame
    finally:
        await source.stop()
    raise AssertionError("fixture produced no frames")


async def test_process_maps_yolo_output_to_detection_events_with_normalized_boxes() -> None:
    names = {0: "person", 2: "car"}
    stub_model = _StubModel(
        [
            [
                _StubResult(
                    names,
                    _StubBoxes(
                        xyxyn=[[0.1, 0.2, 0.5, 0.8], [0.0, 0.0, 1.0, 1.0]],
                        cls=[0.0, 2.0],
                        conf=[0.91, 0.42],
                        id=[1.0, 2.0],
                    ),
                )
            ]
        ]
    )
    detector = YoloObjectDetector(model_path="unused.pt", model=stub_model)
    frame = await _one_real_frame()

    events = await detector.process(frame, context={})

    assert len(events) == 2
    person, car = events
    assert person.event_type == "object_detection.person"
    assert person.metadata["class_label"] == "person"
    assert person.metadata["class_id"] == 0
    assert person.metadata["track_id"] == 1
    assert person.confidence == 0.91
    assert person.bounding_box is not None
    assert (
        person.bounding_box.x_min,
        person.bounding_box.y_min,
        person.bounding_box.x_max,
        person.bounding_box.y_max,
    ) == (0.1, 0.2, 0.5, 0.8)
    assert car.event_type == "object_detection.car"
    assert car.metadata["track_id"] == 2
    assert car.bounding_box is not None


async def test_process_derives_camera_id_from_uuid_shaped_source_id() -> None:
    camera_id = UUID("12345678-1234-5678-1234-567812345678")
    stub_model = _StubModel(
        [
            [
                _StubResult(
                    {0: "person"},
                    _StubBoxes(xyxyn=[[0.0, 0.0, 0.5, 0.5]], cls=[0.0], conf=[0.9], id=[1.0]),
                )
            ]
        ]
    )
    detector = YoloObjectDetector(model_path="unused.pt", model=stub_model)
    frame = await _one_real_frame()
    frame.source_id = str(camera_id)  # simulate a real onboarded camera's source_id

    events = await detector.process(frame, context={})

    assert events[0].camera_id == camera_id


async def test_process_skips_degenerate_boxes_without_raising() -> None:
    stub_model = _StubModel(
        [
            [
                _StubResult(
                    {0: "person"},
                    _StubBoxes(
                        # a zero-width box (x_min == x_max) alongside one valid box
                        xyxyn=[[0.5, 0.5, 0.5, 0.9], [0.1, 0.1, 0.4, 0.4]],
                        cls=[0.0, 0.0],
                        conf=[0.5, 0.6],
                        id=[1.0, 2.0],
                    ),
                )
            ]
        ]
    )
    detector = YoloObjectDetector(model_path="unused.pt", model=stub_model)
    frame = await _one_real_frame()

    events = await detector.process(frame, context={})

    assert len(events) == 1
    assert events[0].confidence == 0.6


async def test_process_calls_model_with_configured_thresholds() -> None:
    stub_model = _StubModel([[_StubResult({}, None)]])
    detector = YoloObjectDetector(
        model_path="unused.pt",
        confidence_threshold=0.6,
        iou_threshold=0.7,
        device="cpu",
        model=stub_model,
    )
    frame = await _one_real_frame()

    events = await detector.process(frame, context={})

    assert events == []
    assert stub_model.calls[0]["conf"] == 0.6
    assert stub_model.calls[0]["iou"] == 0.7
    assert stub_model.calls[0]["device"] == "cpu"
    assert stub_model.calls[0]["persist"] is True
    assert stub_model.calls[0]["tracker"] == "bytetrack.yaml"


async def test_process_surfaces_same_track_id_across_consecutive_frames() -> None:
    """T-110's acceptance bar: the same object keeps one track id across
    consecutive frames/inference calls through the same detector instance."""
    stub_model = _StubModel(
        [
            [
                _StubResult(
                    {0: "person"},
                    _StubBoxes(xyxyn=[[0.1, 0.1, 0.3, 0.3]], cls=[0.0], conf=[0.9], id=[7.0]),
                )
            ],
            [
                _StubResult(
                    {0: "person"},
                    _StubBoxes(xyxyn=[[0.12, 0.11, 0.32, 0.31]], cls=[0.0], conf=[0.88], id=[7.0]),
                )
            ],
        ]
    )
    detector = YoloObjectDetector(model_path="unused.pt", model=stub_model)
    frame = await _one_real_frame()

    first_events = await detector.process(frame, context={})
    second_events = await detector.process(frame, context={})

    assert len(first_events) == 1
    assert len(second_events) == 1
    assert first_events[0].metadata["track_id"] == 7
    assert second_events[0].metadata["track_id"] == 7


async def test_process_surfaces_none_track_id_when_untracked() -> None:
    stub_model = _StubModel(
        [
            [
                _StubResult(
                    {0: "person"},
                    _StubBoxes(xyxyn=[[0.1, 0.1, 0.3, 0.3]], cls=[0.0], conf=[0.9], id=None),
                )
            ]
        ]
    )
    detector = YoloObjectDetector(model_path="unused.pt", model=stub_model)
    frame = await _one_real_frame()

    events = await detector.process(frame, context={})

    assert events[0].metadata["track_id"] is None
