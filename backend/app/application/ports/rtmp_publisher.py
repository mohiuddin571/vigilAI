from abc import ABC, abstractmethod
from pathlib import Path

from app.domain.value_objects.rtmp_publisher_status import RtmpPublisherStatus


class IRtmpPublisher(ABC):
    """Owns one ffmpeg subprocess pushing a local video file to the RTMP demo server.

    Isolated to the RTMP Push/Consume Demo (docs/RTMP_DEMO.md) — not part of
    the graded milestone sequence. Mirrors `IRecordingWorker`'s "use case
    depends on the port, never the concrete ffmpeg subprocess class" shape.
    """

    @abstractmethod
    async def start(self, video_id: str, video_path: Path) -> None:
        """Start publishing `video_path` (looped) to the configured RTMP destination.

        A no-op if already publishing. Raises RtmpPublisherError if the
        ffmpeg subprocess cannot be started at all.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the ffmpeg subprocess gracefully. A no-op if not running."""

    @abstractmethod
    def status(self) -> RtmpPublisherStatus:
        """A point-in-time snapshot of the publisher process."""
