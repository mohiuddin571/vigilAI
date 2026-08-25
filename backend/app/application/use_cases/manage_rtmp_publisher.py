from app.application.ports.demo_video_repository import IDemoVideoRepository
from app.application.ports.rtmp_publisher import IRtmpPublisher
from app.domain.exceptions import DemoVideoNotFoundError
from app.domain.value_objects.rtmp_publisher_status import RtmpPublisherStatus


class ManageRtmpPublisherUseCase:
    """Start/stop/observe the RTMP demo publisher (ffmpeg) — docs/RTMP_DEMO.md.

    Resolves `video_id -> Path` via the existing `IDemoVideoRepository`
    (M17) rather than adding a new file picker — reuses the same
    `storage/demo_videos/` library `/demo` already lists, so this needs no
    new "which video" plumbing and inherits `DemoVideoNotFoundError` for an
    unknown/deleted id (request scenario #9) for free.
    """

    def __init__(
        self, publisher: IRtmpPublisher, demo_video_repository: IDemoVideoRepository
    ) -> None:
        self._publisher = publisher
        self._demo_video_repository = demo_video_repository

    async def execute(self, video_id: str) -> None:
        path = self._demo_video_repository.resolve_path(video_id)
        if path is None:
            raise DemoVideoNotFoundError(f"No demo video with id {video_id!r}")
        await self._publisher.start(video_id, path)

    async def stop(self) -> None:
        await self._publisher.stop()

    def status(self) -> RtmpPublisherStatus:
        return self._publisher.status()
