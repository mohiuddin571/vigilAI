"""T-131: `EasyOcrReader` against a clean, cropped plate image — real EasyOCR
inference, no fake/stub model (docs/TECHNICAL_DECISIONS.md TD-30).

Unlike `test_yolo_detector_integration.py` (which stubs the model because
the *video* fixture has no real COCO object for real inference to find,
TD-25), this test's input is a directly-rendered clean crop, not something
decoded from a video fixture — there's no equivalent obstacle here, and
T-131's own Definition of Done ("given a clean plate crop, returns correct
text in isolated test") is exactly what real inference against a clean crop
demonstrates.
"""

from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.domain.value_objects.plate_number import PlateNumber
from app.infrastructure.analytics.easyocr_reader import EasyOcrReader

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "license_plate.mp4"

# Mirrors generate_license_plate_fixture.py's geometry (also duplicated in
# test_plate_localizer_integration.py) — the known-clean plate crop region.
_WIDTH, _HEIGHT = 640, 480
_VEHICLE_W, _VEHICLE_H = 360, 200
_PLATE_W, _PLATE_H = 160, 40
_VEHICLE_X = _WIDTH // 2 - _VEHICLE_W // 2
_VEHICLE_Y = _HEIGHT // 2 - _VEHICLE_H // 2
_PLATE_X = _VEHICLE_X + (_VEHICLE_W - _PLATE_W) // 2
_PLATE_Y = _VEHICLE_Y + _VEHICLE_H - _PLATE_H - 20

_EXPECTED_TEXT = "VGL1234"


def _clean_plate_crop() -> np.ndarray:
    capture = cv2.VideoCapture(str(_FIXTURE_PATH))
    try:
        ok, frame = capture.read()
        assert ok, "fixture produced no frames"
    finally:
        capture.release()
    return frame[_PLATE_Y : _PLATE_Y + _PLATE_H, _PLATE_X : _PLATE_X + _PLATE_W]


def _reader() -> EasyOcrReader:
    return EasyOcrReader(
        languages=settings.easyocr_languages,
        model_storage_directory=str(settings.easyocr_model_storage_dir),
        gpu=settings.easyocr_gpu,
        min_confidence=settings.easyocr_min_confidence,
    )


async def test_read_returns_correct_text_for_a_clean_plate_crop() -> None:
    crop = _clean_plate_crop()

    result = await _reader().read(crop)

    assert result is not None
    plate_number, confidence = result
    assert plate_number == PlateNumber(value=_EXPECTED_TEXT)
    assert 0.0 <= confidence <= 1.0
    assert confidence > 0.5


async def test_read_returns_none_for_a_blank_crop() -> None:
    blank = np.full((40, 160, 3), 200, dtype=np.uint8)

    result = await _reader().read(blank)

    assert result is None
