from dataclasses import dataclass

from app.domain.exceptions import InvalidDomainStateError


@dataclass(frozen=True)
class DemoVideo:
    """One pre-recorded video file available for the demo video library (M17).

    `id` is a filesystem-safe slug derived from the file's stem (see
    `infrastructure/streaming/local_demo_video_repository.py`), not a
    database-assigned identifier — there is no persistence for demo videos,
    only a directory scan (docs/FOLDER_STRUCTURE.md's convention for
    `storage/demo_videos/`, mirroring `storage/recordings/`).
    """

    id: str
    filename: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidDomainStateError("DemoVideo id must not be empty")
        if not self.filename.strip():
            raise InvalidDomainStateError("DemoVideo filename must not be empty")
