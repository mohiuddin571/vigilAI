from collections.abc import AsyncIterator, Callable

import cv2
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.application.use_cases.list_demo_videos import ListDemoVideosUseCase
from app.application.use_cases.manage_rtmp_publisher import ManageRtmpPublisherUseCase
from app.application.use_cases.manage_rtmp_server import ManageRtmpServerUseCase
from app.application.use_cases.start_rtmp_consumer import StartRtmpConsumerUseCase
from app.domain.entities.frame import Frame
from app.interfaces.schemas.demo_video import DemoVideoResponse
from app.interfaces.schemas.rtmp_demo import (
    RtmpConsumerStatusResponse,
    RtmpPublisherStartRequest,
    RtmpPublisherStatusResponse,
    RtmpServerStatusResponse,
)


def create_rtmp_demo_router(
    build_list_demo_videos_use_case: Callable[[], ListDemoVideosUseCase],
    build_manage_rtmp_server_use_case: Callable[[], ManageRtmpServerUseCase],
    build_manage_rtmp_publisher_use_case: Callable[[], ManageRtmpPublisherUseCase],
    build_start_rtmp_consumer_use_case: Callable[[], StartRtmpConsumerUseCase],
    *,
    mjpeg_boundary: str,
    mjpeg_jpeg_quality: int,
    publish_auth_required: bool,
    read_auth_required: bool,
    configured_video_bitrate_kbps: int,
    consumer_rtmp_url: str,
) -> APIRouter:
    """Build the `/rtmp-demo` router (docs/RTMP_DEMO.md): independently start/stop/observe the
    RTMP demo's server, publisher, and consumer, plus the consumer's MJPEG-over-HTTP playback —
    the same shape `streams.py`/`demo_videos.py` already establish for a live view, reused here
    rather than reinvented. Isolated under its own prefix/module, outside the graded milestone
    sequence.

    `build_manage_rtmp_server_use_case`/`build_manage_rtmp_publisher_use_case`/
    `build_start_rtmp_consumer_use_case` each return the same shared singleton
    on every call (see `container.build_start_live_stream_use_case`'s
    docstring) — they hold state (a running subprocess/Stream Worker) across
    requests, unlike `build_list_demo_videos_use_case`'s per-request factory.
    """
    router = APIRouter(prefix="/rtmp-demo", tags=["rtmp-demo"])

    @router.get("/videos", response_model=list[DemoVideoResponse])
    def list_videos() -> list[DemoVideoResponse]:
        use_case = build_list_demo_videos_use_case()
        return [DemoVideoResponse.from_domain(video) for video in use_case.execute()]

    @router.post("/server/start", status_code=202, response_model=RtmpServerStatusResponse)
    async def start_server() -> RtmpServerStatusResponse:
        use_case = build_manage_rtmp_server_use_case()
        await use_case.execute()
        return RtmpServerStatusResponse.from_status(use_case.status())

    @router.post("/server/stop", status_code=202, response_model=RtmpServerStatusResponse)
    async def stop_server() -> RtmpServerStatusResponse:
        use_case = build_manage_rtmp_server_use_case()
        await use_case.stop()
        return RtmpServerStatusResponse.from_status(use_case.status())

    @router.get("/server/status", response_model=RtmpServerStatusResponse)
    def server_status() -> RtmpServerStatusResponse:
        use_case = build_manage_rtmp_server_use_case()
        return RtmpServerStatusResponse.from_status(use_case.status())

    @router.post("/publisher/start", status_code=202, response_model=RtmpPublisherStatusResponse)
    async def start_publisher(body: RtmpPublisherStartRequest) -> RtmpPublisherStatusResponse:
        use_case = build_manage_rtmp_publisher_use_case()
        await use_case.execute(body.video_id)
        return RtmpPublisherStatusResponse.from_status(
            use_case.status(), publish_auth_required=publish_auth_required
        )

    @router.post("/publisher/stop", status_code=202, response_model=RtmpPublisherStatusResponse)
    async def stop_publisher() -> RtmpPublisherStatusResponse:
        use_case = build_manage_rtmp_publisher_use_case()
        await use_case.stop()
        return RtmpPublisherStatusResponse.from_status(
            use_case.status(), publish_auth_required=publish_auth_required
        )

    @router.get("/publisher/status", response_model=RtmpPublisherStatusResponse)
    def publisher_status() -> RtmpPublisherStatusResponse:
        use_case = build_manage_rtmp_publisher_use_case()
        return RtmpPublisherStatusResponse.from_status(
            use_case.status(), publish_auth_required=publish_auth_required
        )

    @router.post("/consumer/start", status_code=202, response_model=RtmpConsumerStatusResponse)
    async def start_consumer() -> RtmpConsumerStatusResponse:
        use_case = build_start_rtmp_consumer_use_case()
        await use_case.execute()
        return _consumer_response(use_case)

    @router.post("/consumer/stop", status_code=202, response_model=RtmpConsumerStatusResponse)
    async def stop_consumer() -> RtmpConsumerStatusResponse:
        use_case = build_start_rtmp_consumer_use_case()
        await use_case.stop()
        return _consumer_response(use_case)

    @router.get("/consumer/status", response_model=RtmpConsumerStatusResponse)
    def consumer_status() -> RtmpConsumerStatusResponse:
        use_case = build_start_rtmp_consumer_use_case()
        return _consumer_response(use_case)

    @router.get("/consumer/mjpeg")
    async def consumer_mjpeg() -> StreamingResponse:
        use_case = build_start_rtmp_consumer_use_case()
        # Idempotent, same as `streams.py`'s `/mjpeg`: renders in a plain
        # `<img>` tag with no separate "start" call required first.
        await use_case.execute()
        return StreamingResponse(
            _mjpeg_multipart(use_case.frames(), mjpeg_boundary, mjpeg_jpeg_quality),
            media_type=f"multipart/x-mixed-replace; boundary={mjpeg_boundary}",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    def _consumer_response(use_case: StartRtmpConsumerUseCase) -> RtmpConsumerStatusResponse:
        return RtmpConsumerStatusResponse.from_status(
            use_case.health(),
            use_case.diagnostics(),
            configured_video_bitrate_kbps=configured_video_bitrate_kbps,
            read_auth_required=read_auth_required,
            rtmp_url=consumer_rtmp_url,
        )

    return router


async def _mjpeg_multipart(
    frames: AsyncIterator[Frame], boundary: str, jpeg_quality: int
) -> AsyncIterator[bytes]:
    async for frame in frames:
        ok, encoded = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not ok:
            continue
        payload = encoded.tobytes()
        yield (
            f"--{boundary}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(payload)}\r\n\r\n"
        ).encode() + payload + b"\r\n"
