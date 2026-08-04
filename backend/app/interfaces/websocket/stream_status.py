import asyncio
import contextlib
from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.interfaces.schemas.stream import StreamStatusResponse


def create_stream_status_router(
    build_start_live_stream_use_case: Callable[[], StartLiveStreamUseCase],
    *,
    poll_interval_seconds: float,
) -> APIRouter:
    """Build the `/ws/streams/{camera_id}/status` WebSocket channel (T-053).

    Polls `StartLiveStreamUseCase.health()` on a fixed interval and pushes
    the JSON status to the client — simple push-on-poll rather than a full
    pub-sub event bus (that's M8's `IEventPublisher`, out of scope here),
    which is enough for a connection-status indicator that only needs to
    reflect connected/reconnecting/failed within about a second.
    """
    router = APIRouter()

    @router.websocket("/ws/streams/{camera_id}/status")
    async def stream_status_ws(websocket: WebSocket, camera_id: UUID) -> None:
        use_case = build_start_live_stream_use_case()
        await websocket.accept()
        try:
            while True:
                status = StreamStatusResponse.from_health(use_case.health(camera_id))
                await websocket.send_json(status.model_dump(mode="json"))
                await asyncio.sleep(poll_interval_seconds)
        except WebSocketDisconnect:
            pass
        finally:
            with contextlib.suppress(RuntimeError):
                await websocket.close()

    return router
