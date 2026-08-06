from app.application.ports.demo_video_repository import IDemoVideoRepository
from app.domain.entities.demo_video import DemoVideo


class ListDemoVideosUseCase:
    """Lists every video currently available in the demo video library (M17)."""

    def __init__(self, repository: IDemoVideoRepository) -> None:
        self._repository = repository

    def execute(self) -> list[DemoVideo]:
        return self._repository.list_videos()
