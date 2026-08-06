"""M17/T-207: proves the actual seam this feature adds — a demo video's
slug `source_id` (resolved via `IDemoVideoRepository`, never a UUID) flows
through the real analytics pipeline exactly like `Container._build_analytics_frame_source`'s
existing "mp4-demo"/camera branches, and the real License Plate Recognition
plugin (already proven fixture-accurate by
`test_license_plate_recognizer_integration.py`, docs/TECHNICAL_DECISIONS.md
TD-30) still emits a correctly-tagged event over it. Deliberately does not
construct a real `Container` (heavier — real DB, real YOLO/EasyOCR wiring —
and no existing test in this suite does that either; every integration test
here builds its own minimal use-case tree, per `test_streams_api_integration.py`'s
module docstring).
"""

import time
from pathlib import Path

from app.core.config import settings
from app.domain.entities.detection_event import DetectionEvent
from app.infrastructure.analytics.easyocr_reader import EasyOcrReader
from app.infrastructure.analytics.license_plate_recognizer import LicensePlateRecognizer
from app.infrastructure.analytics.orchestrator import AnalyticsOrchestrator
from app.infrastructure.analytics.plate_localizer import PlateLocalizer
from app.infrastructure.streaming.local_demo_video_repository import LocalDemoVideoRepository
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
_EXPECTED_TEXT = "VGL1234"
_RESULT_WAIT_TIMEOUT_SECONDS = 60.0


async def test_demo_video_source_id_resolves_and_emits_lpr_events() -> None:
    repository = LocalDemoVideoRepository(_FIXTURES_DIR)
    video_id = next(
        video.id for video in repository.list_videos() if video.filename == "license_plate.mp4"
    )

    resolved_path = repository.resolve_path(video_id)
    assert resolved_path is not None and resolved_path.name == "license_plate.mp4"

    orchestrator = AnalyticsOrchestrator(
        [
            LicensePlateRecognizer(
                plate_localizer=PlateLocalizer(),
                plate_reader=EasyOcrReader(
                    languages=settings.easyocr_languages,
                    model_storage_directory=str(settings.easyocr_model_storage_dir),
                    gpu=settings.easyocr_gpu,
                    min_confidence=settings.easyocr_min_confidence,
                ),
                queue_max_size=settings.lpr_ocr_queue_max_size,
            )
        ]
    )
    source = Mp4FileFrameSource(file_path=str(resolved_path), source_id=video_id, loop=True)
    await source.start()

    collected: list[DetectionEvent] = []
    try:
        deadline = time.monotonic() + _RESULT_WAIT_TIMEOUT_SECONDS
        frames = source.frames()
        while time.monotonic() < deadline and not collected:
            frame = await frames.__anext__()
            collected.extend(await orchestrator.process(frame))
    finally:
        await source.stop()

    assert len(collected) > 0, "no license_plate_recognition event emitted within the timeout"
    event = collected[0]
    assert event.event_type == f"license_plate_recognition.{_EXPECTED_TEXT}"
    # `camera_id` is `_derive_camera_id(source_id)` (a `uuid5` hash of the
    # slug, since it's never a real UUID) — the raw slug survives untouched
    # in `metadata["source_id"]`, which is what the frontend's
    # `DetectionOverlay` filters on for a non-camera source.
    assert event.metadata["source_id"] == video_id
