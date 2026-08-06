from pathlib import Path

from app.application.ports.demo_video_repository import IDemoVideoRepository
from app.application.use_cases.list_demo_videos import ListDemoVideosUseCase
from app.domain.entities.demo_video import DemoVideo


class FakeDemoVideoRepository(IDemoVideoRepository):
    def __init__(self, videos: list[DemoVideo]) -> None:
        self._videos = videos

    def list_videos(self) -> list[DemoVideo]:
        return self._videos

    def resolve_path(self, video_id: str) -> Path | None:
        raise NotImplementedError


def test_execute_returns_every_video_from_the_repository() -> None:
    videos = [DemoVideo(id="a", filename="a.mp4"), DemoVideo(id="b", filename="b.mp4")]
    use_case = ListDemoVideosUseCase(FakeDemoVideoRepository(videos))

    assert use_case.execute() == videos


def test_execute_returns_empty_list_when_no_videos_are_present() -> None:
    use_case = ListDemoVideosUseCase(FakeDemoVideoRepository([]))

    assert use_case.execute() == []
