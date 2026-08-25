import asyncio
import contextlib
from collections.abc import Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.use_cases.manage_rtmp_publisher import ManageRtmpPublisherUseCase
from app.application.use_cases.manage_rtmp_server import ManageRtmpServerUseCase
from app.application.use_cases.start_rtmp_consumer import StartRtmpConsumerUseCase
from app.interfaces.schemas.rtmp_demo import (
    RtmpConsumerStatusResponse,
    RtmpPublisherStatusResponse,
    RtmpServerStatusResponse,
)


def create_rtmp_demo_status_router(
    build_manage_rtmp_server_use_case: Callable[[], ManageRtmpServerUseCase],
    build_manage_rtmp_publisher_use_case: Callable[[], ManageRtmpPublisherUseCase],
    build_start_rtmp_consumer_use_case: Callable[[], StartRtmpConsumerUseCase],
    *,
    poll_interval_seconds: float,
    publish_auth_required: bool,
    read_auth_required: bool,
    configured_video_bitrate_kbps: int,
    consumer_rtmp_url: str,
) -> APIRouter:
    """Build the `/ws/rtmp-demo/status` WebSocket channel (docs/RTMP_DEMO.md): one combined
    `{server, publisher, consumer}` push per tick, same accept/poll/close shape as
    `stream_status.py`/`demo_stream_status.py`, so the RTMP Demo page's three panels update from a
    single subscription instead of three."""
    router = APIRouter()

    @router.websocket("/ws/rtmp-demo/status")
    async def rtmp_demo_status_ws(websocket: WebSocket) -> None:
        server_use_case = build_manage_rtmp_server_use_case()
        publisher_use_case = build_manage_rtmp_publisher_use_case()
        consumer_use_case = build_start_rtmp_consumer_use_case()
        await websocket.accept()
        try:
            while True:
                payload = {
                    "server": RtmpServerStatusResponse.from_status(
                        server_use_case.status()
                    ).model_dump(mode="json"),
                    "publisher": RtmpPublisherStatusResponse.from_status(
                        publisher_use_case.status(), publish_auth_required=publish_auth_required
                    ).model_dump(mode="json"),
                    "consumer": RtmpConsumerStatusResponse.from_status(
                        consumer_use_case.health(),
                        consumer_use_case.diagnostics(),
                        configured_video_bitrate_kbps=configured_video_bitrate_kbps,
                        read_auth_required=read_auth_required,
                        rtmp_url=consumer_rtmp_url,
                    ).model_dump(mode="json"),
                }
                await websocket.send_json(payload)
                await asyncio.sleep(poll_interval_seconds)
        except WebSocketDisconnect:
            pass
        finally:
            with contextlib.suppress(RuntimeError):
                await websocket.close()

    return router
