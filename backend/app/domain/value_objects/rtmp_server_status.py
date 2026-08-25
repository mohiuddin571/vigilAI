from pydantic import BaseModel, ConfigDict


class RtmpServerStatus(BaseModel):
    """A point-in-time status snapshot of the RTMP demo server (MediaMTX) process.

    Isolated to the RTMP Push/Consume Demo (docs/RTMP_DEMO.md) — not part of
    the graded milestone sequence.
    """

    model_config = ConfigDict(frozen=True)

    running: bool
    pid: int | None = None
    host: str
    port: int
    app_name: str
    stream_key: str
