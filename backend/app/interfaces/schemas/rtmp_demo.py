from pydantic import BaseModel

from app.application.use_cases.start_rtmp_consumer import RtmpConsumerDiagnostics
from app.domain.value_objects.rtmp_publisher_status import RtmpPublisherStatus
from app.domain.value_objects.rtmp_server_status import RtmpServerStatus
from app.domain.value_objects.stream_health import StreamHealth


def display_rtmp_url(host: str, port: int, app_name: str, stream_key: str) -> str:
    """Credential-free RTMP URL for UI display — never the publish/read-credential-bearing form
    `infrastructure/rtmp_demo/ffmpeg_publisher.py`'s `build_rtmp_url` constructs for the actual
    connection (TD-15: interfaces never handles real credentials, so it only ever needs this
    display form)."""
    return f"rtmp://{host}:{port}/{app_name}/{stream_key}"


class RtmpPublisherStartRequest(BaseModel):
    """Request body for `POST /rtmp-demo/publisher/start`."""

    video_id: str


class RtmpServerStatusResponse(BaseModel):
    """Response/WS-message shape for the RTMP demo server (MediaMTX) panel."""

    running: bool
    pid: int | None
    host: str
    port: int
    app_name: str
    stream_key: str
    rtmp_url: str

    @classmethod
    def from_status(cls, status: RtmpServerStatus) -> "RtmpServerStatusResponse":
        return cls(
            running=status.running,
            pid=status.pid,
            host=status.host,
            port=status.port,
            app_name=status.app_name,
            stream_key=status.stream_key,
            rtmp_url=display_rtmp_url(status.host, status.port, status.app_name, status.stream_key),
        )


class RtmpPublisherStatusResponse(BaseModel):
    """Response/WS-message shape for the RTMP demo publisher (ffmpeg) panel."""

    running: bool
    pid: int | None
    video_id: str | None
    exited_unexpectedly: bool
    error: str | None
    publish_auth_required: bool

    @classmethod
    def from_status(
        cls, status: RtmpPublisherStatus, *, publish_auth_required: bool
    ) -> "RtmpPublisherStatusResponse":
        return cls(
            running=status.running,
            pid=status.pid,
            video_id=status.video_id,
            exited_unexpectedly=status.exited_unexpectedly,
            error=status.error,
            publish_auth_required=publish_auth_required,
        )


class RtmpConsumerStatusResponse(BaseModel):
    """Response/WS-message shape for the RTMP demo consumer + video diagnostics panel.

    `configured_codec`/`configured_video_bitrate_kbps` reflect the
    publisher's own encode settings, not something independently measured
    from the decoded stream — `cv2.VideoCapture`'s FFmpeg backend doesn't
    reliably expose true codec/bitrate for a network source. Labeled
    "configured" rather than presented as a live measurement, so the UI
    never implies a precision this pipeline doesn't actually have (see
    docs/TECHNICAL_DECISIONS.md TD-30's precedent for stating such
    limitations honestly).
    """

    state: str
    last_frame_at: str | None
    consecutive_failures: int
    last_error: str | None
    observed_resolution: tuple[int, int] | None
    observed_fps: float | None
    configured_codec: str
    configured_video_bitrate_kbps: int
    read_auth_required: bool
    rtmp_url: str

    @classmethod
    def from_status(
        cls,
        health: StreamHealth,
        diagnostics: RtmpConsumerDiagnostics,
        *,
        configured_video_bitrate_kbps: int,
        read_auth_required: bool,
        rtmp_url: str,
    ) -> "RtmpConsumerStatusResponse":
        return cls(
            state=health.state.value,
            last_frame_at=health.last_frame_at.isoformat() if health.last_frame_at else None,
            consecutive_failures=health.consecutive_failures,
            last_error=health.last_error,
            observed_resolution=diagnostics.resolution,
            observed_fps=diagnostics.observed_fps,
            configured_codec="H264",
            configured_video_bitrate_kbps=configured_video_bitrate_kbps,
            read_auth_required=read_auth_required,
            rtmp_url=rtmp_url,
        )
