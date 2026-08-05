import asyncio
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import NAMESPACE_DNS, UUID, uuid5

import structlog

from app.application.ports.detector_plugin import IDetectorPlugin
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.domain.value_objects.bounding_box import BoundingBox

logger = structlog.get_logger(__name__)

# Reserved `context` key (docs/ARCHITECTURE.md §6.4, TD-27): the one narrow,
# documented exception to "plugins must never read another plugin's private
# key out of context" (IDetectorPlugin's docstring). Written here, per
# `frame.source_id` (not overwritten globally — the single shared
# `AnalyticsOrchestrator` serves multiple concurrent sources, TD-24/TD-26),
# so `ColorDetector` can read this frame's bounding boxes without re-running
# detection.
EVENTS_BY_SOURCE_CONTEXT_KEY = "yolo_object_detector.events_by_source"


class _YoloBoxes(Protocol):
    """The subset of `ultralytics.engine.results.Boxes` this plugin reads."""

    @property
    def xyxyn(self) -> Any: ...  # tensor -> .tolist() gives [[x1,y1,x2,y2], ...] normalized [0,1]

    @property
    def cls(self) -> Any: ...  # tensor -> .tolist() gives class indices (as floats)

    @property
    def conf(self) -> Any: ...  # tensor -> .tolist() gives confidences

    @property
    def id(self) -> Any: ...  # tensor -> .tolist() gives per-box ByteTrack ids; None if untracked


class _YoloResult(Protocol):
    names: dict[int, str]
    boxes: _YoloBoxes | None


class _YoloModel(Protocol):
    """The subset of `ultralytics.YOLO`'s tracking inference interface this
    plugin depends on — narrow on purpose so tests can inject a lightweight
    fake instead of loading real model weights (see
    docs/TECHNICAL_DECISIONS.md TD-25's testing note)."""

    def track(
        self,
        source: Any,
        *,
        conf: float,
        iou: float,
        device: str | None,
        verbose: bool,
        persist: bool,
        tracker: str,
    ) -> Sequence[_YoloResult]: ...


def _load_model(model_path: str) -> Any:
    # Imported lazily (not at module load time): `ultralytics`/`torch` are
    # heavy to import, and this keeps the module importable in tests that
    # inject a fake model without ever touching the real dependency.
    # Returns `Any`, not `_YoloModel`, deliberately: the real `YOLO.__call__`
    # signature (multiple accepted input types, `stream`/`**kwargs`) is wider
    # than the narrow structural `_YoloModel` protocol this plugin actually
    # uses — that protocol exists for tests to inject a lightweight fake
    # against, not to pin the real class's full public interface.
    from ultralytics import YOLO  # type: ignore[attr-defined]

    return YOLO(model_path)


def _derive_camera_id(source_id: str) -> UUID:
    """Real onboarded cameras use their own `Camera.id` as `source_id`
    (docs/TECHNICAL_DECISIONS.md TD-25) — used directly so events join the
    real `camera` row. Non-UUID sources (e.g. the `"mp4-demo"` fixture) fall
    back to the same deterministic `uuid5` derivation `NoOpDetectorPlugin`
    uses (TD-24 decision 4), so repeated runs of the same demo source still
    correlate to one id.
    """
    try:
        return UUID(source_id)
    except ValueError:
        return uuid5(NAMESPACE_DNS, source_id)


def _clamped_bounding_box(
    x_min: float, y_min: float, x_max: float, y_max: float
) -> BoundingBox | None:
    """Clamp a YOLO box to `[0, 1]` and drop it if it's degenerate after clamping.

    `BoundingBox` validates strictly (`x_min < x_max`); real inference output
    is occasionally right at the frame edge (e.g. `1.0000001` from float
    rounding) or, rarely, a zero-width box — this plugin skips those rather
    than letting one bad box raise through and drop the whole frame's
    otherwise-valid detections.
    """
    x_min, x_max = sorted((min(max(x_min, 0.0), 1.0), min(max(x_max, 0.0), 1.0)))
    y_min, y_max = sorted((min(max(y_min, 0.0), 1.0), min(max(y_max, 0.0), 1.0)))
    if x_min >= x_max or y_min >= y_max:
        return None
    return BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


class YoloObjectDetector(IDetectorPlugin):
    """Real object detection + classification + tracking via one Ultralytics
    YOLO call (T-091, T-110).

    Detection and classification come from a single `model.track()` inference
    call (docs/TECHNICAL_DECISIONS.md TD-06) — there is no separate
    classification pass; each returned box already carries its class label.
    `model.track()` (bundled ByteTrack, `tracker="bytetrack.yaml"`,
    `persist=True`) is a mode change on that same call, not a second
    detection/tracking system (TD-06) — it additionally assigns each box a
    persistent track id, surfaced as `DetectionEvent.metadata["track_id"]`.

    One model instance is loaded lazily per `source_id` (not one global
    model), keyed in `self._models`, rather than sharing a single model
    across every analytics-enabled source. This matters specifically because
    of `persist=True`: Ultralytics keeps ByteTrack's tracker state on the
    model/predictor instance itself, so interleaving frames from different
    concurrently-enabled sources through one shared model would let track ids
    bleed across sources — and `Container.__init__` wires exactly one shared
    `YoloObjectDetector` across every analytics-enabled
    `RunAnalyticsPipelineUseCase` (docs/TECHNICAL_DECISIONS.md TD-24/TD-25).
    Keying model instances by `source_id` resolves this entirely inside this
    class, with no composition-root change — see TD-26.

    The model is loaded lazily on first `process()` for a given source (not
    in `__init__`), so constructing this plugin never triggers a network
    download or device allocation before it's actually used. `model_path`
    points at `storage/models/` (gitignored) via `Settings.yolo_model_path`
    — see `_load_model`'s docstring-equivalent note in
    docs/TECHNICAL_DECISIONS.md TD-25 for why this alone satisfies T-090's
    "cold start downloads once, cached thereafter" (Ultralytics' own loader
    downloads-if-missing to exactly the path given).

    Also writes this frame's `DetectionEvent`s into `context` under
    `EVENTS_BY_SOURCE_CONTEXT_KEY`, keyed by `frame.source_id`, so
    `ColorDetector` (T-100) can read this frame's bounding boxes for the
    same source without re-running detection — see this module's constant
    docstring and docs/TECHNICAL_DECISIONS.md TD-27.

    Inference runs via `asyncio.to_thread` — a plain thread, not a separate
    `multiprocessing` process — so the blocking, CPU-bound `model.track()`
    call never stalls the asyncio event loop
    `RunAnalyticsPipelineUseCase.execute()` runs in
    (docs/AI_PROJECT_CONTEXT.md §8's "sync/process-isolated where CPU-bound"
    principle, TD-05). See TD-25 for why a thread was judged sufficient for
    this milestone rather than jumping straight to process isolation.
    """

    def __init__(
        self,
        model_path: str,
        *,
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        device: str | None = None,
        model: _YoloModel | None = None,
    ) -> None:
        self._model_path = model_path
        self._confidence_threshold = confidence_threshold
        self._iou_threshold = iou_threshold
        self._device = device
        # Injectable for tests: bypasses per-source loading entirely, every
        # source uses this same fake instance. None means "load lazily, one
        # instance per source_id" (see class docstring for why per-source).
        self._injected_model = model
        self._models: dict[str, _YoloModel] = {}
        self._load_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def plugin_id(self) -> str:
        return "yolo_object_detector"

    async def _get_model(self, source_id: str) -> _YoloModel:
        if self._injected_model is not None:
            return self._injected_model
        if source_id not in self._models:
            async with self._load_locks[source_id]:
                if source_id not in self._models:
                    self._models[source_id] = await asyncio.to_thread(_load_model, self._model_path)
        return self._models[source_id]

    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        model = await self._get_model(frame.source_id)
        results = await asyncio.to_thread(
            model.track,
            frame.image,
            conf=self._confidence_threshold,
            iou=self._iou_threshold,
            device=self._device,
            verbose=False,
            persist=True,
            tracker="bytetrack.yaml",
        )

        camera_id = _derive_camera_id(frame.source_id)
        occurred_at = datetime.now(UTC)
        events: list[DetectionEvent] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            xyxyn_list = boxes.xyxyn.tolist()
            track_ids = boxes.id.tolist() if boxes.id is not None else [None] * len(xyxyn_list)
            for xyxyn, cls_value, conf_value, track_id_value in zip(
                xyxyn_list, boxes.cls.tolist(), boxes.conf.tolist(), track_ids, strict=True
            ):
                bounding_box = _clamped_bounding_box(*xyxyn)
                if bounding_box is None:
                    logger.debug(
                        "yolo_detector.degenerate_box_skipped",
                        source_id=frame.source_id,
                        frame_sequence=frame.sequence,
                    )
                    continue
                class_id = int(cls_value)
                label = result.names[class_id]
                track_id = int(track_id_value) if track_id_value is not None else None
                events.append(
                    DetectionEvent(
                        camera_id=camera_id,
                        event_type=f"object_detection.{label}",
                        occurred_at=occurred_at,
                        confidence=min(max(float(conf_value), 0.0), 1.0),
                        bounding_box=bounding_box,
                        metadata={
                            "source_id": frame.source_id,
                            "frame_sequence": frame.sequence,
                            "class_id": class_id,
                            "class_label": label,
                            "track_id": track_id,
                        },
                    )
                )
        context.setdefault(EVENTS_BY_SOURCE_CONTEXT_KEY, {})[frame.source_id] = events
        return events
