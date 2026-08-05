"""T-132/T-133/T-134: `LicensePlateRecognizer` end-to-end against the
committed plate-visible fixture (docs/TECHNICAL_DECISIONS.md TD-30).

- T-132: an end-to-end MP4 run emits a `DetectionEvent` with recognized
  plate text.
- T-133: a *measured* test that `process()`'s own latency is unaffected by
  OCR runtime — the queued/background-task design this module documents.
- T-134: sampled-frame accuracy against the fixture, recorded honestly
  (see TD-30 for the exact observed number).
"""

import asyncio
import time
from pathlib import Path

import cv2

from app.core.config import settings
from app.domain.entities.frame import Frame
from app.domain.value_objects.plate_number import PlateNumber
from app.infrastructure.analytics.easyocr_reader import EasyOcrReader
from app.infrastructure.analytics.license_plate_recognizer import LicensePlateRecognizer
from app.infrastructure.analytics.plate_localizer import PlateLocalizer
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "license_plate.mp4"
_EXPECTED_TEXT = "VGL1234"
_RESULT_WAIT_TIMEOUT_SECONDS = 60.0


def _real_plugin() -> LicensePlateRecognizer:
    return LicensePlateRecognizer(
        plate_localizer=PlateLocalizer(),
        plate_reader=EasyOcrReader(
            languages=settings.easyocr_languages,
            model_storage_directory=str(settings.easyocr_model_storage_dir),
            gpu=settings.easyocr_gpu,
            min_confidence=settings.easyocr_min_confidence,
        ),
        queue_max_size=settings.lpr_ocr_queue_max_size,
    )


class _SlowFakeReader:
    """A fake `ILicensePlateReader` with a controllable artificial delay,
    used to measure T-133 without depending on real EasyOCR's own latency
    (which varies by machine/cold-vs-warm-model-load)."""

    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds

    async def read(self, plate_crop: object) -> tuple[PlateNumber, float] | None:
        await asyncio.sleep(self._delay_seconds)
        return PlateNumber(value=_EXPECTED_TEXT), 0.99


async def _one_real_frame(source_id: str = "lpr-fixture") -> Frame:
    source = Mp4FileFrameSource(file_path=str(_FIXTURE_PATH), source_id=source_id, loop=False)
    await source.start()
    try:
        async for frame in source.frames():
            return frame
    finally:
        await source.stop()
    raise AssertionError("fixture produced no frames")


async def test_process_returns_immediately_despite_slow_ocr_reader() -> None:
    """T-133, measured directly: `process()`'s own latency must not scale
    with OCR runtime — a reader that takes several seconds must not make
    `process()` take several seconds too."""
    plugin = LicensePlateRecognizer(
        plate_localizer=PlateLocalizer(),
        plate_reader=_SlowFakeReader(delay_seconds=3.0),
        queue_max_size=10,
    )
    frame = await _one_real_frame()

    started_at = time.monotonic()
    await plugin.process(frame, context={})
    elapsed_seconds = time.monotonic() - started_at

    assert elapsed_seconds < 1.0, (
        f"process() took {elapsed_seconds:.2f}s despite a 3.0s-delay reader — "
        "OCR is stalling the per-frame call, not running off it"
    )


async def test_queued_result_eventually_surfaces_via_process() -> None:
    """Complements the latency test above: confirms the "queued" half of
    "async/queued execution" (T-133's own wording) — a slow read isn't
    silently dropped, it surfaces on a later `process()` call once the
    background worker finishes it."""
    plugin = LicensePlateRecognizer(
        plate_localizer=PlateLocalizer(),
        plate_reader=_SlowFakeReader(delay_seconds=0.2),
        queue_max_size=10,
    )
    frame = await _one_real_frame()

    first_events = await plugin.process(frame, context={})
    assert first_events == []  # too soon — the background read hasn't finished yet

    deadline = time.monotonic() + 5.0
    collected = []
    while time.monotonic() < deadline and not collected:
        await asyncio.sleep(0.05)
        collected = await plugin.process(frame, context={})

    assert len(collected) == 1
    assert collected[0].event_type == f"license_plate_recognition.{_EXPECTED_TEXT}"


async def test_end_to_end_emits_detection_event_with_plate_text() -> None:
    """T-132: a live/MP4 run through the real localizer + real EasyOCR
    eventually emits a `DetectionEvent` with the correct recognized text."""
    plugin = _real_plugin()
    source = Mp4FileFrameSource(file_path=str(_FIXTURE_PATH), source_id="lpr-e2e", loop=True)
    await source.start()

    collected: list = []
    try:
        deadline = time.monotonic() + _RESULT_WAIT_TIMEOUT_SECONDS
        frames = source.frames()
        while time.monotonic() < deadline and not collected:
            frame = await frames.__anext__()
            collected.extend(await plugin.process(frame, context={}))
    finally:
        await source.stop()

    assert len(collected) > 0, "no license_plate_recognition event emitted within the timeout"
    event = collected[0]
    assert event.event_type == f"license_plate_recognition.{_EXPECTED_TEXT}"
    assert event.metadata["plate_text"] == _EXPECTED_TEXT
    assert event.bounding_box is not None
    assert 0.0 <= event.confidence <= 1.0


async def test_accuracy_on_sampled_fixture_frames() -> None:
    """T-134: sample multiple frames, recognize each independently (real
    localizer + real EasyOCR, called synchronously so this test doesn't
    depend on the background queue's timing), and record the observed
    match rate honestly — see docs/TECHNICAL_DECISIONS.md TD-30 for the
    number this produced and what it means."""
    localizer = PlateLocalizer()
    reader = EasyOcrReader(
        languages=settings.easyocr_languages,
        model_storage_directory=str(settings.easyocr_model_storage_dir),
        gpu=settings.easyocr_gpu,
        min_confidence=settings.easyocr_min_confidence,
    )

    capture = cv2.VideoCapture(str(_FIXTURE_PATH))
    sampled_images = []
    try:
        index = 0
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if index % 5 == 0:
                sampled_images.append(image)
            index += 1
    finally:
        capture.release()
    assert len(sampled_images) > 0

    correct = 0
    for image in sampled_images:
        candidates = localizer.locate(image)
        recognized_text = None
        for box in candidates:
            height, width = image.shape[:2]
            x_min, x_max = int(box.x_min * width), int(box.x_max * width)
            y_min, y_max = int(box.y_min * height), int(box.y_max * height)
            crop = image[y_min:y_max, x_min:x_max]
            result = await reader.read(crop)
            if result is not None and result[0].value == _EXPECTED_TEXT:
                recognized_text = result[0].value
                break
        if recognized_text == _EXPECTED_TEXT:
            correct += 1

    match_rate = correct / len(sampled_images)
    # IMPLEMENTATION_PLAN.md §M13 AC #1, literally: "at least a majority of
    # sampled frames" — TD-30 records the exact observed rate.
    assert match_rate > 0.5, f"only {correct}/{len(sampled_images)} sampled frames matched"
