"""T-084/T-085: exercises the real `/analytics` router + WebSocket events channel end
to end — a real `AnalyticsSessionRegistry`, `RunAnalyticsPipelineUseCase`,
`AnalyticsOrchestrator`/`NoOpDetectorPlugin`, `SupervisedFrameSource` wrapping a real
`Mp4FileFrameSource` against the committed fixture, and a real `EventBus` fanning out
to both `SqlEventRepository` and `AnalyticsEventsHub`.
"""

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.use_cases.analytics_session_registry import AnalyticsSessionRegistry
from app.application.use_cases.list_detection_events import ListDetectionEventsUseCase
from app.application.use_cases.run_analytics_pipeline import RunAnalyticsPipelineUseCase
from app.core.exception_handlers import register_exception_handlers
from app.infrastructure.analytics.noop_plugin import NoOpDetectorPlugin
from app.infrastructure.analytics.orchestrator import AnalyticsOrchestrator
from app.infrastructure.messaging.event_bus import EventBus
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.event_repository import SqlEventRepository
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource
from app.infrastructure.streaming.supervised_frame_source import SupervisedFrameSource
from app.interfaces.api.analytics import create_analytics_router
from app.interfaces.websocket.analytics_events import (
    AnalyticsEventsHub,
    create_analytics_events_router,
)

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"
_SOURCE_ID = "mp4-demo"


async def _build_app(db_path: Path) -> FastAPI:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    event_repository = SqlEventRepository(build_session_factory(engine))
    event_bus = EventBus()
    hub = AnalyticsEventsHub()
    event_bus.subscribe(event_repository.add)
    event_bus.subscribe(hub.broadcast)
    orchestrator = AnalyticsOrchestrator([NoOpDetectorPlugin()])

    async def build_use_case(source_id: str) -> RunAnalyticsPipelineUseCase:
        frame_source = SupervisedFrameSource(
            Mp4FileFrameSource(file_path=str(_FIXTURE_PATH), source_id=source_id),
            backoff_schedule=[0.1],
        )
        return RunAnalyticsPipelineUseCase(frame_source, orchestrator.process, event_bus)

    registry = AnalyticsSessionRegistry(build_use_case)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        create_analytics_router(
            lambda: registry, lambda: ListDetectionEventsUseCase(event_repository)
        )
    )
    app.include_router(create_analytics_events_router(hub))
    return app


def test_enabling_analytics_delivers_events_over_websocket_and_via_list_api(
    tmp_path: Path,
) -> None:
    app = asyncio.run(_build_app(tmp_path / "analytics.db"))
    with TestClient(app) as client:
        with client.websocket_connect("/ws/analytics/events") as websocket:
            enable_response = client.post(f"/analytics/{_SOURCE_ID}/enable")
            assert enable_response.status_code == 202
            assert enable_response.json() == {"source_id": _SOURCE_ID, "enabled": True}

            message = websocket.receive_json()
            assert message["event_type"] == "noop.frame_processed"
            assert message["metadata"]["source_id"] == _SOURCE_ID

        status_response = client.get(f"/analytics/{_SOURCE_ID}/status")
        assert status_response.json() == {"source_id": _SOURCE_ID, "enabled": True}

        list_response = client.get("/analytics/events")
        assert list_response.status_code == 200
        events = list_response.json()
        assert len(events) >= 1
        assert events[0]["event_type"] == "noop.frame_processed"


def test_disabling_analytics_stops_new_events(tmp_path: Path) -> None:
    app = asyncio.run(_build_app(tmp_path / "analytics.db"))
    with TestClient(app) as client:
        with client.websocket_connect("/ws/analytics/events") as websocket:
            client.post(f"/analytics/{_SOURCE_ID}/enable")
            websocket.receive_json()  # at least one event has been published

        disable_response = client.post(f"/analytics/{_SOURCE_ID}/disable")
        assert disable_response.json() == {"source_id": _SOURCE_ID, "enabled": False}

        count_at_disable = len(client.get("/analytics/events").json())
        time.sleep(0.3)
        count_after_wait = len(client.get("/analytics/events").json())

        assert count_after_wait == count_at_disable
