"""EasyOCR-backed `ILicensePlateReader` (T-131, docs/TECHNICAL_DECISIONS.md TD-07/TD-30)."""

import asyncio
from typing import Any, Protocol

import structlog
from pydantic import ValidationError

from app.application.ports.license_plate_reader import ILicensePlateReader
from app.domain.value_objects.plate_number import PlateNumber

logger = structlog.get_logger(__name__)

# Plates are alphanumeric only (`PlateNumber`'s own validator additionally
# allows space/hyphen, but restricting EasyOCR's own candidate character set
# up front reduces misreads of punctuation/symbols as plate characters).
_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class _EasyOcrReaderProtocol(Protocol):
    """The subset of `easyocr.Reader` this module depends on — narrow on
    purpose so tests can inject a lightweight fake (mirrors
    `yolo_detector._YoloModel`'s equivalent protocol, TD-25)."""

    def readtext(
        self, image: Any, *, detail: int, allowlist: str
    ) -> list[tuple[Any, str, float]]: ...


def _load_reader(languages: list[str], model_storage_directory: str, gpu: bool) -> Any:
    # Imported lazily (not at module load time): `easyocr`/`torch` are heavy
    # to import — same reasoning as `yolo_detector._load_model` (TD-25).
    import easyocr

    return easyocr.Reader(
        languages,
        gpu=gpu,
        model_storage_directory=model_storage_directory,
        download_enabled=True,
        verbose=False,
    )


class EasyOcrReader(ILicensePlateReader):
    """Reads plate text from an already-localized plate-region crop (T-131).

    The `easyocr.Reader` model is loaded lazily on first `read()` call (not
    in `__init__`), mirroring `YoloObjectDetector`'s lazy model load (TD-25)
    — constructing this class never triggers a model download.
    `model_storage_directory` points at the gitignored `storage/models/easyocr/`
    (`docs/FOLDER_STRUCTURE.md`'s already-documented convention for cached
    EasyOCR weights, alongside YOLO's `.pt` files).

    `readtext()` (blocking, CPU/MPS-bound) runs via `asyncio.to_thread`, the
    same pattern `YoloObjectDetector.process()` uses for its blocking
    inference call (TD-05/TD-25) — this alone keeps a single `read()` call
    from stalling the asyncio event loop. `LicensePlateRecognizer` (T-133)
    additionally runs `read()` off a background queue so a slow OCR call
    doesn't stall its own per-frame loop either — see that module.

    When a crop yields more than one detected text region (e.g. a small
    state/country caption above the plate number), only the
    highest-confidence region's text is used — concatenating every detected
    fragment risks merging unrelated text into one invalid string. A read
    below `min_confidence`, or text that doesn't parse as a `PlateNumber`
    (garbage/symbols), is treated the same as "no text could be read":
    returns `None` per `ILicensePlateReader`'s own contract, never raises.
    """

    def __init__(
        self,
        *,
        languages: list[str],
        model_storage_directory: str,
        gpu: bool = False,
        min_confidence: float = 0.3,
        reader: _EasyOcrReaderProtocol | None = None,
    ) -> None:
        self._languages = languages
        self._model_storage_directory = model_storage_directory
        self._gpu = gpu
        self._min_confidence = min_confidence
        # Injectable for tests: bypasses the real model entirely, same
        # precedent as `YoloObjectDetector`'s `model` constructor arg.
        self._injected_reader = reader
        self._reader: _EasyOcrReaderProtocol | None = None
        self._load_lock = asyncio.Lock()

    async def _get_reader(self) -> _EasyOcrReaderProtocol:
        if self._injected_reader is not None:
            return self._injected_reader
        if self._reader is None:
            async with self._load_lock:
                if self._reader is None:
                    self._reader = await asyncio.to_thread(
                        _load_reader, self._languages, self._model_storage_directory, self._gpu
                    )
        assert self._reader is not None  # guaranteed by the double-checked block above
        return self._reader

    async def read(self, plate_crop: Any) -> tuple[PlateNumber, float] | None:
        reader = await self._get_reader()
        results = await asyncio.to_thread(
            reader.readtext, plate_crop, detail=1, allowlist=_ALLOWLIST
        )
        if not results:
            return None

        _, text, confidence = max(results, key=lambda result: result[2])
        confidence = min(max(float(confidence), 0.0), 1.0)
        if confidence < self._min_confidence:
            return None

        try:
            plate_number = PlateNumber(value=text)
        except ValidationError:
            logger.debug("easyocr_reader.unparseable_text", raw_text=text, confidence=confidence)
            return None

        return plate_number, confidence
