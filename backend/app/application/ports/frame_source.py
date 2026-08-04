from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class IFrameSource(ABC):
    """Yields frames from a video source (ONVIF camera, raw RTSP, or MP4 file).

    This is the load-bearing abstraction of the whole project: every detector
    depends on this interface only, never on ONVIF/RTSP specifics (see
    docs/AI_PROJECT_CONTEXT.md §4).

    The yielded frame type is `Any` in this milestone — the concrete `Frame`
    domain object is finalized in M2 (docs/TASK_BACKLOG.md T-020), which is
    out of scope here. This port will be tightened to reference `Frame` once
    it exists.
    """

    @abstractmethod
    async def start(self) -> None:
        """Begin producing frames."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop producing frames and release any underlying resources."""

    @abstractmethod
    def frames(self) -> AsyncIterator[Any]:
        """An async iterator yielding frames for as long as the source is running."""
