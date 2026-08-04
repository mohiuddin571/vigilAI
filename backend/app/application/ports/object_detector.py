from abc import ABC, abstractmethod
from typing import Any

from app.domain.entities.detection_event import DetectionEvent


class IObjectDetector(ABC):
    """Runs detection/classification over a single frame.

    Takes `Any` for the frame parameter until `Frame` is finalized in M2
    (docs/TASK_BACKLOG.md T-020) — see IFrameSource for the same note.
    """

    @abstractmethod
    async def detect(self, frame: Any) -> list[DetectionEvent]: ...
