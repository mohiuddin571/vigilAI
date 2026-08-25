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
from app.interfaces.api.demo_videos import create_demo_videos_router
from app.interfaces.api.recordings import create_recordings_router
from app.interfaces.api.rtmp_demo import create_rtmp_demo_router
from app.interfaces.api.stream_debug import create_stream_debug_router
from app.interfaces.api.streams import create_streams_router
from app.interfaces.api.zones import create_zones_router
from app.interfaces.schemas.rtmp_demo import display_rtmp_url
from app.interfaces.websocket.analytics_events import create_analytics_events_router
from app.interfaces.websocket.demo_stream_status import create_demo_stream_status_router
from app.interfaces.websocket.rtmp_demo_status import create_rtmp_demo_status_router
from app.interfaces.websocket.stream_status import create_stream_status_router

configure_logging()

container = Container(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await container.init_db()
    yield
    # Stops every running Stream/Recording Worker subprocess on a graceful
    # shutdown (Ctrl+C / SIGTERM) — see `Container.shutdown`'s docstring for
    # the orphaned-process incident this closes. Only reachable if the
    # process actually gets to exit cleanly: `kill -9`/SIGKILL skips this
    # entirely, which is exactly why that must never be used to stop this
    # server (see README's "Stopping the backend" note).
    await container.shutdown()


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
        build_update_camera_use_case=container.build_update_camera_use_case,
        build_delete_camera_use_case=container.build_delete_camera_use_case,
        build_update_camera_analytics_settings_use_case=(
            container.build_update_camera_analytics_settings_use_case
        ),
        known_detector_types=container.known_detector_types,
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
    create_demo_videos_router(
        container.build_list_demo_videos_use_case,
        container.build_start_demo_stream_use_case,
        mjpeg_boundary=settings.mjpeg_boundary,
        mjpeg_jpeg_quality=settings.mjpeg_jpeg_quality,
    )
)
app.include_router(
    create_demo_stream_status_router(
        container.build_start_demo_stream_use_case,
        poll_interval_seconds=settings.stream_status_poll_interval_seconds,
    )
)
app.include_router(
    create_recordings_router(
        container.build_start_recording_use_case,
        container.build_stop_recording_use_case,
        container.build_list_recordings_use_case,
        container.build_get_recording_use_case,
        container.build_delete_recording_use_case,
    )
)
app.include_router(
    create_analytics_router(
        container.build_analytics_session_registry,
        container.build_list_detection_events_use_case,
        container.build_clear_detection_events_use_case,
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

# RTMP Push/Consume Demo (docs/RTMP_DEMO.md) — isolated, outside the graded
# milestone sequence. `_rtmp_publish_auth_required`/`_rtmp_read_auth_required`
# and the consumer's display URL are resolved once here (composition root),
# same as `mjpeg_boundary`/`mjpeg_jpeg_quality` above, rather than the
# interfaces layer reaching into `settings` directly.
_rtmp_publish_auth_required = bool(
    settings.rtmp_publish_username and settings.rtmp_publish_password
)
_rtmp_read_auth_required = bool(settings.rtmp_read_username and settings.rtmp_read_password)
_rtmp_consumer_url = display_rtmp_url(
    settings.rtmp_server_host,
    settings.rtmp_server_port,
    settings.rtmp_app_name,
    settings.rtmp_stream_key,
)
app.include_router(
    create_rtmp_demo_router(
        container.build_list_demo_videos_use_case,
        container.build_manage_rtmp_server_use_case,
        container.build_manage_rtmp_publisher_use_case,
        container.build_start_rtmp_consumer_use_case,
        mjpeg_boundary=settings.mjpeg_boundary,
        mjpeg_jpeg_quality=settings.mjpeg_jpeg_quality,
        publish_auth_required=_rtmp_publish_auth_required,
        read_auth_required=_rtmp_read_auth_required,
        configured_video_bitrate_kbps=settings.rtmp_publish_video_bitrate_kbps,
        consumer_rtmp_url=_rtmp_consumer_url,
    )
)
app.include_router(
    create_rtmp_demo_status_router(
        container.build_manage_rtmp_server_use_case,
        container.build_manage_rtmp_publisher_use_case,
        container.build_start_rtmp_consumer_use_case,
        poll_interval_seconds=settings.stream_status_poll_interval_seconds,
        publish_auth_required=_rtmp_publish_auth_required,
        read_auth_required=_rtmp_read_auth_required,
        configured_video_bitrate_kbps=settings.rtmp_publish_video_bitrate_kbps,
        consumer_rtmp_url=_rtmp_consumer_url,
    )
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
