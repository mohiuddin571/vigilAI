"""`LicensePlateRecognizer` detector plugin (T-132, T-133).

Composes `PlateLocalizer` (T-130) + an `ILicensePlateReader` (T-131,
`EasyOcrReader`) into one `IDetectorPlugin`, emitting `DetectionEvent`s with
recognized plate text + confidence.
"""

import asyncio
import contextlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

import numpy as np
import structlog

from app.application.ports.detector_plugin import IDetectorPlugin
from app.application.ports.license_plate_reader import ILicensePlateReader
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.domain.value_objects.bounding_box import BoundingBox
from app.infrastructure.analytics.plate_localizer import PlateLocalizer

logger = structlog.get_logger(__name__)

_EVENT_TYPE_PREFIX = "license_plate_recognition"


def _derive_camera_id(source_id: str) -> UUID:
    """Duplicated from `yolo_detector._derive_camera_id`/
    `missing_object_detector._derive_camera_id` rather than imported across
    modules — same precedent TD-25/TD-29 already established for this exact
    small, private helper."""
    try:
        return UUID(source_id)
    except ValueError:
        return uuid5(NAMESPACE_DNS, source_id)


def _crop_bounding_box(image: np.ndarray, box: BoundingBox) -> np.ndarray | None:
    """Duplicated from `color_detector._crop_bounding_box` — same small-
    private-helper duplication precedent (TD-25) rather than a cross-module
    import of a leading-underscore function."""
    height, width = image.shape[:2]
    x_min = min(max(int(box.x_min * width), 0), width)
    x_max = min(max(int(box.x_max * width), x_min + 1), width)
    y_min = min(max(int(box.y_min * height), 0), height)
    y_max = min(max(int(box.y_max * height), y_min + 1), height)
    if x_min >= x_max or y_min >= y_max:
        return None
    return image[y_min:y_max, x_min:x_max]


@dataclass
class _PendingRead:
    """One localized plate candidate, queued for background OCR."""

    camera_id: UUID
    bounding_box: BoundingBox
    crop: np.ndarray
    source_id: str
    frame_sequence: int
    occurred_at: datetime


class LicensePlateRecognizer(IDetectorPlugin):
    """Composes `PlateLocalizer` + an `ILicensePlateReader` into one
    detector plugin (T-132), emitting `DetectionEvent`s with recognized
    plate text + confidence.

    Runs independently of `YoloObjectDetector`'s same-frame `context`
    (docs/TECHNICAL_DECISIONS.md TD-30) — localizes candidates over the
    *full* frame, not gated behind vehicle-class boxes; see that entry for
    why (gating on YOLO's vehicle detections would produce zero candidates
    against this milestone's own synthetic test fixture).

    **Non-blocking OCR (T-133)**: `process()` never awaits OCR inline.
    Localizing candidate regions (classical CV, wrapped in
    `asyncio.to_thread` since it's heavier per-call than `ColorDetector`'s
    single `cv2.cvtColor`) enqueues each candidate crop onto a bounded,
    drop-oldest `asyncio.Queue` **per `source_id`** (mirroring
    `YoloObjectDetector`'s per-source keying/double-checked-locking
    pattern, TD-26 — avoids one source's OCR backlog affecting another's
    turnaround through the single shared `AnalyticsOrchestrator`, TD-24). A
    lazily-started background `asyncio.Task` per source drains that queue,
    calls the injected `ILicensePlateReader.read()` (itself already
    `asyncio.to_thread`-wrapped inside `EasyOcrReader`), and puts any
    successful read onto a per-source *result* queue. Each `process()` call
    then does a **non-blocking** drain of that result queue and returns
    whatever's ready.

    Consequence, documented rather than hidden: a `DetectionEvent` for a
    plate localized on frame N may only actually surface (be returned from
    `process()`, and therefore published) on some later frame N+k, once its
    background OCR read has completed — never necessarily on frame N
    itself. This is the tradeoff that makes OCR latency genuinely not stall
    this or any other source's per-frame loop (measured directly in
    `test_license_plate_recognizer_integration.py`), rather than merely
    keeping the asyncio event loop unblocked the way a bare inline
    `await asyncio.to_thread(...)` would.

    A per-item read failure is caught and logged rather than propagated —
    unlike `RunAnalyticsPipelineUseCase.execute()`'s frame loop (which has
    no try/except around plugin calls, by design), this background worker
    has no external supervisor to notice a dead task (the same class of gap
    TD-26's addendum documents), so letting one bad crop kill the whole
    worker permanently would silently stop all future OCR for that source.
    """

    def __init__(
        self,
        plate_localizer: PlateLocalizer,
        plate_reader: ILicensePlateReader,
        *,
        queue_max_size: int = 10,
    ) -> None:
        self._plate_localizer = plate_localizer
        self._plate_reader = plate_reader
        self._queue_max_size = queue_max_size
        self._input_queues: dict[str, asyncio.Queue[_PendingRead]] = {}
        self._result_queues: dict[str, asyncio.Queue[DetectionEvent]] = {}
        self._worker_tasks: dict[str, asyncio.Task[None]] = {}
        self._worker_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def plugin_id(self) -> str:
        return "license_plate_recognizer"

    async def _ensure_worker(self, source_id: str) -> "asyncio.Queue[_PendingRead]":
        if source_id not in self._input_queues:
            async with self._worker_locks[source_id]:
                if source_id not in self._input_queues:
                    self._input_queues[source_id] = asyncio.Queue(maxsize=self._queue_max_size)
                    self._result_queues[source_id] = asyncio.Queue()
                    self._worker_tasks[source_id] = asyncio.create_task(
                        self._run_worker(source_id), name=f"lpr-worker-{source_id}"
                    )
        return self._input_queues[source_id]

    async def _run_worker(self, source_id: str) -> None:
        input_queue = self._input_queues[source_id]
        result_queue = self._result_queues[source_id]
        while True:
            pending = await input_queue.get()
            try:
                result = await self._plate_reader.read(pending.crop)
            except Exception:
                logger.exception("license_plate_recognizer.read_failed", source_id=source_id)
                continue
            if result is None:
                continue
            plate_number, confidence = result
            await result_queue.put(
                DetectionEvent(
                    camera_id=pending.camera_id,
                    event_type=f"{_EVENT_TYPE_PREFIX}.{plate_number.value}",
                    occurred_at=pending.occurred_at,
                    confidence=confidence,
                    bounding_box=pending.bounding_box,
                    metadata={
                        "source_id": pending.source_id,
                        "frame_sequence": pending.frame_sequence,
                        "plate_text": plate_number.value,
                    },
                )
            )

    def _enqueue_candidates(
        self,
        frame: Frame,
        boxes: list[BoundingBox],
        input_queue: "asyncio.Queue[_PendingRead]",
    ) -> None:
        camera_id = _derive_camera_id(frame.source_id)
        occurred_at = datetime.now(UTC)
        for box in boxes:
            crop = _crop_bounding_box(frame.image, box)
            if crop is None:
                continue
            pending = _PendingRead(
                camera_id=camera_id,
                bounding_box=box,
                crop=crop,
                source_id=frame.source_id,
                frame_sequence=frame.sequence,
                occurred_at=occurred_at,
            )
            try:
                input_queue.put_nowait(pending)
            except asyncio.QueueFull:
                # Drop-oldest (same policy as the Stream Worker's frame
                # queue, TD-20): discard the stalest pending crop to make
                # room, rather than blocking this frame's process() call.
                with contextlib.suppress(asyncio.QueueEmpty):
                    input_queue.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    input_queue.put_nowait(pending)

    def _drain_results(self, source_id: str) -> list[DetectionEvent]:
        result_queue = self._result_queues.get(source_id)
        if result_queue is None:
            return []
        events: list[DetectionEvent] = []
        while not result_queue.empty():
            events.append(result_queue.get_nowait())
        return events

    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        candidates = await asyncio.to_thread(self._plate_localizer.locate, frame.image)
        if candidates:
            input_queue = await self._ensure_worker(frame.source_id)
            self._enqueue_candidates(frame, candidates, input_queue)
        return self._drain_results(frame.source_id)
