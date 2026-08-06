from abc import ABC, abstractmethod
from pathlib import Path

from app.domain.entities.demo_video import DemoVideo


class IDemoVideoRepository(ABC):
    """Lists and resolves the operator-provided demo video library (M17).

    Kept behind a port for the same reason as `IRecordingFileStore` — the
    application layer stays I/O-free, with a concrete filesystem scan living
    in `infrastructure/streaming/local_demo_video_repository.py`.
    """

    @abstractmethod
    def list_videos(self) -> list[DemoVideo]:
        """Every demo video currently present in the configured directory."""

    @abstractmethod
    def resolve_path(self, video_id: str) -> Path | None:
        """The file path for `video_id`, or `None` if it doesn't match a
        video currently present in the configured directory. Never raises
        for path-traversal attempts — an id that isn't one just-listed
        (see `list_videos`) simply resolves to `None`, by construction."""
