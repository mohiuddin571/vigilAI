import asyncio
import contextlib
from collections.abc import Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.use_cases.start_demo_stream import StartDemoStreamUseCase
from app.interfaces.schemas.stream import StreamStatusResponse


def create_demo_stream_status_router(
    build_start_demo_stream_use_case: Callable[[], StartDemoStreamUseCase],
    *,
    poll_interval_seconds: float,
) -> APIRouter:
    """Build the `/ws/demo/videos/{video_id}/status` WebSocket channel (M17),
    a small duplicate of `stream_status.py`'s camera equivalent (T-053) keyed
    by `video_id: str` instead of `camera_id: UUID`."""
    router = APIRouter()

    @router.websocket("/ws/demo/videos/{video_id}/status")
    async def demo_stream_status_ws(websocket: WebSocket, video_id: str) -> None:
        use_case = build_start_demo_stream_use_case()
        await websocket.accept()
        try:
            while True:
                status = StreamStatusResponse.from_health(use_case.health(video_id))
                await websocket.send_json(status.model_dump(mode="json"))
                await asyncio.sleep(poll_interval_seconds)
        except WebSocketDisconnect:
            pass
        finally:
            with contextlib.suppress(RuntimeError):
                await websocket.close()

    return router
