from pydantic import BaseModel, ConfigDict


class RtmpPublisherStatus(BaseModel):
    """A point-in-time status snapshot of the RTMP demo publisher (ffmpeg) process.

    Isolated to the RTMP Push/Consume Demo (docs/RTMP_DEMO.md) — not part of
    the graded milestone sequence.
    """

    model_config = ConfigDict(frozen=True)

    running: bool
    pid: int | None = None
    video_id: str | None = None
    # True when the ffmpeg process exited on its own (bad/corrupt input,
    # server unreachable, auth rejected, ...) rather than via `stop()` —
    # distinguishes "publisher stopped unexpectedly" (request scenario #7)
    # from a deliberate stop in the status the UI reports.
    exited_unexpectedly: bool = False
    error: str | None = None
