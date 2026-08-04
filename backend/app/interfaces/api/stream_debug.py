from fastapi import APIRouter

from app.application.use_cases.debug_stream import DebugStreamUseCase
from app.interfaces.schemas.stream_debug import DebugStreamStatusResponse


def create_stream_debug_router(debug_stream_use_case: DebugStreamUseCase) -> APIRouter:
    """Build the `/debug/streams/mp4` router (T-025).

    Dev/demo tooling only, proving the M2 Stream Worker produces frames from
    the committed MP4 fixture and survives simulated disconnect — not the
    real live-view endpoint (`interfaces/api/streams.py`, MJPEG-over-HTTP
    against a resolved RTSP source, is M5's `T-052`).

    Unlike `cameras.py`'s per-request use-case factories, `debug_stream_use_case`
    is a single shared instance built once by the composition root: its whole
    purpose is to hold one running Stream Worker across requests (start once,
    poll status, stop once), not to isolate per-request mutable state.
    """
    router = APIRouter(prefix="/debug/streams/mp4", tags=["debug"])

    @router.post("/start", status_code=202)
    async def start() -> DebugStreamStatusResponse:
        await debug_stream_use_case.start()
        return DebugStreamStatusResponse.from_dto(debug_stream_use_case.status())

    @router.post("/stop", status_code=202)
    async def stop() -> DebugStreamStatusResponse:
        await debug_stream_use_case.stop()
        return DebugStreamStatusResponse.from_dto(debug_stream_use_case.status())

    @router.get("/status")
    async def status() -> DebugStreamStatusResponse:
        return DebugStreamStatusResponse.from_dto(debug_stream_use_case.status())

    return router
