from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter

from app.application.use_cases.analytics_session_registry import AnalyticsSessionRegistry
from app.application.use_cases.list_detection_events import ListDetectionEventsUseCase
from app.interfaces.schemas.analytics import AnalyticsStatusResponse, DetectionEventResponse


def create_analytics_router(
    build_analytics_session_registry: Callable[[], AnalyticsSessionRegistry],
    build_list_detection_events_use_case: Callable[[], ListDetectionEventsUseCase],
) -> APIRouter:
    """Build the `/analytics` router (T-085): enable/disable/status per source + event listing.

    `build_analytics_session_registry` returns the same shared singleton on
    every call (mirrors `streams.py`'s `build_start_live_stream_use_case`) —
    it holds running analytics sessions across requests.
    `build_list_detection_events_use_case` is a per-request factory: that
    use case is stateless.
    """
    router = APIRouter(prefix="/analytics", tags=["analytics"])

    @router.post("/{source_id}/enable", status_code=202, response_model=AnalyticsStatusResponse)
    async def enable(source_id: str) -> AnalyticsStatusResponse:
        registry = build_analytics_session_registry()
        await registry.enable(source_id)
        return AnalyticsStatusResponse(source_id=source_id, enabled=registry.is_enabled(source_id))

    @router.post("/{source_id}/disable", status_code=202, response_model=AnalyticsStatusResponse)
    async def disable(source_id: str) -> AnalyticsStatusResponse:
        registry = build_analytics_session_registry()
        await registry.disable(source_id)
        return AnalyticsStatusResponse(source_id=source_id, enabled=registry.is_enabled(source_id))

    @router.get("/{source_id}/status", response_model=AnalyticsStatusResponse)
    async def status(source_id: str) -> AnalyticsStatusResponse:
        registry = build_analytics_session_registry()
        return AnalyticsStatusResponse(source_id=source_id, enabled=registry.is_enabled(source_id))

    @router.get("/events", response_model=list[DetectionEventResponse])
    async def list_events(
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DetectionEventResponse]:
        events = await build_list_detection_events_use_case().execute(
            camera_id, event_type, start, end
        )
        return [DetectionEventResponse.from_domain(event) for event in events]

    return router
