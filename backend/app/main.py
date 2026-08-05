from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.container import Container
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.interfaces.api.analytics import create_analytics_router
from app.interfaces.api.cameras import create_cameras_router
from app.interfaces.api.recordings import create_recordings_router
from app.interfaces.api.stream_debug import create_stream_debug_router
from app.interfaces.api.streams import create_streams_router
from app.interfaces.api.zones import create_zones_router
from app.interfaces.websocket.analytics_events import create_analytics_events_router
from app.interfaces.websocket.stream_status import create_stream_status_router

configure_logging()

container = Container(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await container.init_db()
    yield


app = FastAPI(title="VigilAI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(
    create_cameras_router(
        build_onboard_camera_use_case=container.build_onboard_camera_use_case,
        build_list_cameras_use_case=container.build_list_cameras_use_case,
        build_get_camera_use_case=container.build_get_camera_use_case,
        build_get_camera_config_use_case=container.build_get_camera_config_use_case,
        build_update_camera_config_use_case=container.build_update_camera_config_use_case,
        build_update_camera_rtsp_override_use_case=container.build_update_camera_rtsp_override_use_case,
    )
)
app.include_router(create_stream_debug_router(container.build_debug_stream_use_case()))
app.include_router(
    create_streams_router(
        container.build_start_live_stream_use_case,
        mjpeg_boundary=settings.mjpeg_boundary,
        mjpeg_jpeg_quality=settings.mjpeg_jpeg_quality,
    )
)
app.include_router(
    create_stream_status_router(
        container.build_start_live_stream_use_case,
        poll_interval_seconds=settings.stream_status_poll_interval_seconds,
    )
)
app.include_router(
    create_recordings_router(
        container.build_start_recording_use_case,
        container.build_stop_recording_use_case,
        container.build_list_recordings_use_case,
        container.build_get_recording_use_case,
    )
)
app.include_router(
    create_analytics_router(
        container.build_analytics_session_registry,
        container.build_list_detection_events_use_case,
    )
)
app.include_router(create_analytics_events_router(container.build_analytics_events_hub()))
app.include_router(
    create_zones_router(
        container.build_create_zone_use_case,
        container.build_list_zones_by_camera_use_case,
        container.build_get_zone_use_case,
        container.build_update_zone_use_case,
        container.build_delete_zone_use_case,
    )
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
