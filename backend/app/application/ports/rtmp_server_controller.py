from abc import ABC, abstractmethod

from app.domain.value_objects.rtmp_server_status import RtmpServerStatus


class IRtmpServerController(ABC):
    """Owns the lifecycle of the RTMP demo's ingest/serving process (MediaMTX).

    Isolated to the RTMP Push/Consume Demo (docs/RTMP_DEMO.md) — not part of
    the graded milestone sequence. Mirrors `IRecordingWorker`'s "use case
    depends on the port, never the concrete subprocess class" shape.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the RTMP server process. A no-op if already running.

        Raises RtmpServerUnavailableError if the subprocess cannot be started.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the RTMP server process gracefully. A no-op if not running."""

    @abstractmethod
    def status(self) -> RtmpServerStatus:
        """A point-in-time snapshot of the server process."""
