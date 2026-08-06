import re
from pathlib import Path

from app.application.ports.demo_video_repository import IDemoVideoRepository
from app.domain.entities.demo_video import DemoVideo

_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9-]+")


def _slugify(stem: str) -> str:
    slug = _NON_SLUG_CHARS.sub("-", stem.lower()).strip("-")
    return slug or "video"


class LocalDemoVideoRepository(IDemoVideoRepository):
    """Scans a directory of operator-provided video files (M17, T-205).

    No caching/DB, no file-watching — re-scans `videos_dir` on every call.
    Deliberately simple: this directory is expected to hold a handful of
    files a person drops in before a demo, not something that churns fast
    enough to need anything more (docs/AGENTS.md "smallest change" bias).

    `resolve_path` only ever returns a path this same scan just found under
    `videos_dir` — it never joins caller-supplied input onto a filesystem
    path, so an arbitrary/traversal-shaped `video_id` (e.g. `"../../etc/passwd"`)
    simply fails to match any slug and resolves to `None`, by construction
    rather than by a denylist check.
    """

    def __init__(self, videos_dir: Path) -> None:
        self._videos_dir = videos_dir

    def _scan(self) -> dict[str, Path]:
        if not self._videos_dir.is_dir():
            return {}
        by_id: dict[str, Path] = {}
        for path in sorted(self._videos_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in _VIDEO_EXTENSIONS:
                continue
            slug = _slugify(path.stem)
            candidate = slug
            suffix = 2
            while candidate in by_id:
                candidate = f"{slug}-{suffix}"
                suffix += 1
            by_id[candidate] = path
        return by_id

    def list_videos(self) -> list[DemoVideo]:
        return [
            DemoVideo(id=video_id, filename=path.name) for video_id, path in self._scan().items()
        ]

    def resolve_path(self, video_id: str) -> Path | None:
        return self._scan().get(video_id)
