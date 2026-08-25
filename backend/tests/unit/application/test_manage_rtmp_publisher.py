from pathlib import Path

import pytest

from app.application.ports.demo_video_repository import IDemoVideoRepository
from app.application.ports.rtmp_publisher import IRtmpPublisher
from app.application.use_cases.manage_rtmp_publisher import ManageRtmpPublisherUseCase
from app.domain.entities.demo_video import DemoVideo
from app.domain.exceptions import DemoVideoNotFoundError
from app.domain.value_objects.rtmp_publisher_status import RtmpPublisherStatus


class FakeDemoVideoRepository(IDemoVideoRepository):
    def __init__(self, paths: dict[str, Path]) -> None:
        self._paths = paths

    def list_videos(self) -> list[DemoVideo]:
        return [
            DemoVideo(id=video_id, filename=path.name) for video_id, path in self._paths.items()
        ]

    def resolve_path(self, video_id: str) -> Path | None:
        return self._paths.get(video_id)


class FakeRtmpPublisher(IRtmpPublisher):
    """A fake `IRtmpPublisher` double — no ffmpeg subprocess, no I/O."""

    def __init__(self) -> None:
        self.started_with: tuple[str, Path] | None = None
        self.stopped = False

    async def start(self, video_id: str, video_path: Path) -> None:
        self.started_with = (video_id, video_path)
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True
        self.started_with = None

    def status(self) -> RtmpPublisherStatus:
        if self.started_with is None:
            return RtmpPublisherStatus(running=False)
        video_id, _ = self.started_with
        return RtmpPublisherStatus(running=True, pid=5678, video_id=video_id)


def _build_use_case(
    paths: dict[str, Path], publisher: FakeRtmpPublisher | None = None
) -> tuple[ManageRtmpPublisherUseCase, FakeRtmpPublisher]:
    publisher = publisher if publisher is not None else FakeRtmpPublisher()
    return (
        ManageRtmpPublisherUseCase(publisher, FakeDemoVideoRepository(paths)),
        publisher,
    )


async def test_execute_raises_demo_video_not_found_for_unknown_id() -> None:
    use_case, _ = _build_use_case({})
    with pytest.raises(DemoVideoNotFoundError):
        await use_case.execute("unknown")


async def test_execute_starts_the_publisher_with_the_resolved_path() -> None:
    use_case, publisher = _build_use_case({"car-1": Path("/videos/car-1.mp4")})

    await use_case.execute("car-1")

    assert publisher.started_with == ("car-1", Path("/videos/car-1.mp4"))
    assert use_case.status().running is True
    assert use_case.status().video_id == "car-1"


async def test_stop_stops_the_publisher() -> None:
    use_case, publisher = _build_use_case({"car-1": Path("/videos/car-1.mp4")})
    await use_case.execute("car-1")

    await use_case.stop()

    assert publisher.stopped is True
    assert use_case.status().running is False


async def test_stop_is_a_no_op_when_never_started() -> None:
    use_case, _ = _build_use_case({})
    await use_case.stop()  # must not raise
    assert use_case.status().running is False
