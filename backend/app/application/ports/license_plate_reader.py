from abc import ABC, abstractmethod
from typing import Any

from app.domain.value_objects.plate_number import PlateNumber


class ILicensePlateReader(ABC):
    """Reads plate text from an already-localized plate region crop.

    Takes `Any` for the crop parameter until `Frame` is finalized in M2
    (docs/TASK_BACKLOG.md T-020) — see IFrameSource for the same note.
    """

    @abstractmethod
    async def read(self, plate_crop: Any) -> tuple[PlateNumber, float] | None:
        """Returns (plate number, confidence), or None if no text could be read."""
