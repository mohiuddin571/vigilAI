from abc import ABC, abstractmethod

from app.domain.entities.recording import Recording


class IRecordingWorker(ABC):
    """Owns one FFmpeg stream-copy segment-muxer subprocess recording a camera's RTSP source.

    Added at M6 (docs/TECHNICAL_DECISIONS.md TD-22), mirroring `IStreamWorker`'s
    role for live streaming: the use case depends on this port, never on the
    concrete FFmpeg subprocess class directly.
    """

    @abstractmethod
    async def start(self) -> Recording:
        """Start the ffmpeg subprocess.

        Returns an in-progress `Recording` (`ended_at=None`, `size_bytes=None`)
        for the first segment file this session will write — not yet
        persisted, the caller is responsible for that. `stop()`'s first
        returned segment reuses this same `Recording.id`.

        Raises FrameSourceUnavailableError if the subprocess cannot be
        started at all.
        """

    @abstractmethod
    async def stop(self) -> list[Recording]:
        """Stop the ffmpeg subprocess gracefully; return one `Recording` per finalized segment.

        Empty list if no segment file was ever successfully finalized (e.g.
        the RTSP source never actually became readable despite the process
        starting). `segments[0].id` is the same id `start()` returned.
        """
