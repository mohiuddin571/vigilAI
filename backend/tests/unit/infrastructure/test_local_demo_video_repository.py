from pathlib import Path

from app.infrastructure.streaming.local_demo_video_repository import LocalDemoVideoRepository


def _touch(path: Path) -> None:
    path.write_bytes(b"not a real video, just needs to exist")


def test_missing_directory_lists_nothing(tmp_path: Path) -> None:
    repository = LocalDemoVideoRepository(tmp_path / "does-not-exist")
    assert repository.list_videos() == []
    assert repository.resolve_path("anything") is None


def test_lists_only_recognized_video_extensions(tmp_path: Path) -> None:
    _touch(tmp_path / "parking-lot.mp4")
    _touch(tmp_path / "entrance.MOV")
    _touch(tmp_path / "notes.txt")

    videos = {video.filename for video in LocalDemoVideoRepository(tmp_path).list_videos()}

    assert videos == {"parking-lot.mp4", "entrance.MOV"}


def test_slugifies_filenames_into_ids(tmp_path: Path) -> None:
    _touch(tmp_path / "Front Gate Cam #1.mp4")

    videos = LocalDemoVideoRepository(tmp_path).list_videos()

    assert len(videos) == 1
    assert videos[0].id == "front-gate-cam-1"


def test_slug_collisions_get_a_stable_suffix(tmp_path: Path) -> None:
    _touch(tmp_path / "clip.mp4")
    _touch(tmp_path / "clip.mov")

    videos = sorted(LocalDemoVideoRepository(tmp_path).list_videos(), key=lambda v: v.filename)

    assert {video.id for video in videos} == {"clip", "clip-2"}


def test_resolve_path_returns_the_matching_file(tmp_path: Path) -> None:
    _touch(tmp_path / "parking-lot.mp4")
    repository = LocalDemoVideoRepository(tmp_path)

    resolved = repository.resolve_path("parking-lot")

    assert resolved == tmp_path / "parking-lot.mp4"


def test_resolve_path_rejects_unknown_or_traversal_ids(tmp_path: Path) -> None:
    _touch(tmp_path / "parking-lot.mp4")
    repository = LocalDemoVideoRepository(tmp_path)

    assert repository.resolve_path("unknown-id") is None
    assert repository.resolve_path("../../etc/passwd") is None
