from collections.abc import AsyncIterator, Callable

import cv2
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.application.use_cases.list_demo_videos import ListDemoVideosUseCase
from app.application.use_cases.start_demo_stream import StartDemoStreamUseCase
from app.domain.entities.frame import Frame
from app.interfaces.schemas.demo_video import DemoVideoResponse
from app.interfaces.schemas.stream import StreamStatusResponse


def create_demo_videos_router(
    build_list_demo_videos_use_case: Callable[[], ListDemoVideosUseCase],
    build_start_demo_stream_use_case: Callable[[], StartDemoStreamUseCase],
    *,
    mjpeg_boundary: str,
    mjpeg_jpeg_quality: int,
) -> APIRouter:
    """Build the `/demo/videos` router (M17, T-206): list the demo video
    library and start/stop/status/MJPEG-stream one entry, keyed by
    `video_id: str` (a `DemoVideo.id` slug) rather than `streams.py`'s
    `camera_id: UUID` — same MJPEG-over-HTTP shape as that router (T-052),
    duplicated rather than imported since the two routers key on different
    id types and have different not-found semantics (`DemoVideoNotFoundError`
    vs `CameraNotFoundError`).
    """
    router = APIRouter(prefix="/demo/videos", tags=["demo"])

    @router.get("", response_model=list[DemoVideoResponse])
    def list_videos() -> list[DemoVideoResponse]:
        use_case = build_list_demo_videos_use_case()
        return [DemoVideoResponse.from_domain(video) for video in use_case.execute()]

    @router.post("/{video_id}/start", status_code=202, response_model=StreamStatusResponse)
    async def start_stream(video_id: str) -> StreamStatusResponse:
        use_case = build_start_demo_stream_use_case()
        await use_case.execute(video_id)
        return StreamStatusResponse.from_health(use_case.health(video_id))

    @router.post("/{video_id}/stop", status_code=202, response_model=StreamStatusResponse)
    async def stop_stream(video_id: str) -> StreamStatusResponse:
        use_case = build_start_demo_stream_use_case()
        await use_case.stop(video_id)
        return StreamStatusResponse.from_health(use_case.health(video_id))

    @router.get("/{video_id}/status", response_model=StreamStatusResponse)
    async def stream_status(video_id: str) -> StreamStatusResponse:
        use_case = build_start_demo_stream_use_case()
        return StreamStatusResponse.from_health(use_case.health(video_id))

    @router.get("/{video_id}/mjpeg")
    async def mjpeg(video_id: str) -> StreamingResponse:
        use_case = build_start_demo_stream_use_case()
        # Idempotent, same as `streams.py`'s `/mjpeg`: renders in a plain
        # `<img>` tag with no separate "start" call required first.
        await use_case.execute(video_id)
        return StreamingResponse(
            _mjpeg_multipart(use_case.frames(video_id), mjpeg_boundary, mjpeg_jpeg_quality),
            media_type=f"multipart/x-mixed-replace; boundary={mjpeg_boundary}",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
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
