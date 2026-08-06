from collections.abc import AsyncIterator, Callable
from uuid import UUID

import cv2
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.domain.entities.frame import Frame
from app.interfaces.schemas.stream import StreamStatusResponse


def create_streams_router(
    build_start_live_stream_use_case: Callable[[], StartLiveStreamUseCase],
    *,
    mjpeg_boundary: str,
    mjpeg_jpeg_quality: int,
) -> APIRouter:
    """Build the `/streams` router (T-052): MJPEG-over-HTTP live view + start/stop/status.

    `build_start_live_stream_use_case` returns the same shared singleton on
    every call (see `container.build_start_live_stream_use_case`'s docstring)
    — unlike `cameras.py`'s per-request use-case factories, this one must
    hold state (running Stream Workers) across requests.
    """
    router = APIRouter(prefix="/streams", tags=["streams"])

    @router.post("/{camera_id}/start", status_code=202, response_model=StreamStatusResponse)
    async def start_stream(camera_id: UUID) -> StreamStatusResponse:
        use_case = build_start_live_stream_use_case()
        await use_case.execute(camera_id)
        return StreamStatusResponse.from_health(use_case.health(camera_id))

    @router.post("/{camera_id}/stop", status_code=202, response_model=StreamStatusResponse)
    async def stop_stream(camera_id: UUID) -> StreamStatusResponse:
        use_case = build_start_live_stream_use_case()
        await use_case.stop(camera_id)
        return StreamStatusResponse.from_health(use_case.health(camera_id))

    @router.get("/{camera_id}/status", response_model=StreamStatusResponse)
    async def stream_status(camera_id: UUID) -> StreamStatusResponse:
        use_case = build_start_live_stream_use_case()
        return StreamStatusResponse.from_health(use_case.health(camera_id))

    @router.get("/{camera_id}/mjpeg")
    async def mjpeg(camera_id: UUID) -> StreamingResponse:
        use_case = build_start_live_stream_use_case()
        # Idempotent: renders in a plain `<img>` tag with no separate "start"
        # call required first (T-052 DoD), while `/start`/`/stop` above stay
        # available for explicit connect/disconnect control from the UI.
        await use_case.execute(camera_id)
        return StreamingResponse(
            _mjpeg_multipart(use_case.frames(camera_id), mjpeg_boundary, mjpeg_jpeg_quality),
            media_type=f"multipart/x-mixed-replace; boundary={mjpeg_boundary}",
            # Without this, browsers can serve a later <img src="/mjpeg"> mount
            # (switching tabs, or the Dashboard tile vs. Camera Detail using
            # the identical URL) from a cached copy of an earlier response
            # instead of opening a fresh multipart connection, which renders
            # as one frozen frame until a full page reload.
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
