from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.entities.frame import Frame
from app.domain.value_objects.stream_health import StreamHealth


class IStreamWorker(ABC):
    """Supervises one `IFrameSource`'s lifecycle: connect, read, detect disconnect, reconnect.

    This is "the M2 Stream Worker abstraction" that `StartLiveStreamUseCase`
    (M5) and any future use case wrap a real source with — it's what lets a
    use case depend on frame-producing infrastructure without importing a
    concrete FFmpeg/OpenCV/RTSP class directly (Dependency Direction Rule,
    docs/FOLDER_STRUCTURE.md).

    Implemented by `infrastructure/streaming/StreamWorker`, which runs the
    supervised read loop in a separate OS process (docs/TECHNICAL_DECISIONS.md
    TD-05) and bridges frames/health back via bounded, drop-oldest queues.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the supervised lifecycle. Idempotent if already running."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the supervised lifecycle and release any underlying resources."""

    @abstractmethod
    def frames(self) -> AsyncIterator[Frame]:
        """An async iterator yielding frames for as long as the worker is running."""

    @abstractmethod
    def health(self) -> StreamHealth:
        """The most recently observed health snapshot."""
