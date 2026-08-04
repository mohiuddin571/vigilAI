from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.entities.frame import Frame


class IFrameSource(ABC):
    """Yields frames from a video source (ONVIF camera, raw RTSP, or MP4 file).

    This is the load-bearing abstraction of the whole project: every detector
    depends on this interface only, never on ONVIF/RTSP specifics (see
    docs/AI_PROJECT_CONTEXT.md §4).

    Deliberately has no `health()` method: a source only knows open/closed,
    not "reconnecting" — that supervision concern belongs to whatever wraps
    it (`IStreamWorker`, M2 T-023/T-024), so any source (MP4, RTSP, ...) can
    be supervised by the same reconnect/backoff policy without needing to
    implement retry logic itself (docs/ARCHITECTURE.md §6.2).
    """

    @property
    @abstractmethod
    def source_id(self) -> str:
        """A stable identifier for this source, used to correlate frames/logs."""

    @abstractmethod
    async def start(self) -> None:
        """Begin producing frames.

        Raises FrameSourceUnavailableError if the source cannot be opened.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop producing frames and release any underlying resources."""

    @abstractmethod
    def frames(self) -> AsyncIterator[Frame]:
        """An async iterator yielding frames for as long as the source is running."""
