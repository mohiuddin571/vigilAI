"""T-111: exercises the real `/zones` router end to end — real use cases over
a real `SqlAnalyticsZoneRepository` against a temporary SQLite file, proving
the zone CRUD API's Definition of Done ("zone persists, retrievable per
camera") through HTTP, not just the repository directly.
"""

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.create_zone import CreateZoneUseCase
from app.application.use_cases.delete_zone import DeleteZoneUseCase
from app.application.use_cases.get_zone import GetZoneUseCase
from app.application.use_cases.list_zones_by_camera import ListZonesByCameraUseCase
from app.application.use_cases.update_zone import UpdateZoneUseCase
from app.core.exception_handlers import register_exception_handlers
from app.infrastructure.persistence.analytics_zone_repository import SqlAnalyticsZoneRepository
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.interfaces.api.zones import create_zones_router


async def _build_app(db_path: Path) -> FastAPI:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    zone_repository = SqlAnalyticsZoneRepository(build_session_factory(engine))

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        create_zones_router(
            lambda: CreateZoneUseCase(zone_repository),
            lambda: ListZonesByCameraUseCase(zone_repository),
            lambda: GetZoneUseCase(zone_repository),
            lambda: UpdateZoneUseCase(zone_repository),
            lambda: DeleteZoneUseCase(zone_repository),
        )
    )
    return app


async def test_zone_persists_and_is_retrievable_per_camera(tmp_path: Path) -> None:
    app = await _build_app(tmp_path / "zones.db")
    camera_id = uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/zones",
            json={
                "camera_id": str(camera_id),
                "name": "Entrance",
                "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
                "dwell_threshold_seconds": 5.0,
                "missing_object_threshold_seconds": 30.0,
            },
        )
        assert create_response.status_code == 201
        zone_id = create_response.json()["id"]

        list_response = await client.get("/zones", params={"camera_id": str(camera_id)})
        assert list_response.status_code == 200
        listed = list_response.json()
        assert len(listed) == 1
        assert listed[0]["id"] == zone_id
        assert listed[0]["name"] == "Entrance"
        assert listed[0]["dwell_threshold_seconds"] == 5.0
        assert listed[0]["missing_object_threshold_seconds"] == 30.0

        get_response = await client.get(f"/zones/{zone_id}")
        assert get_response.status_code == 200
        assert get_response.json()["camera_id"] == str(camera_id)


async def test_update_zone_persists_the_change(tmp_path: Path) -> None:
    app = await _build_app(tmp_path / "zones.db")
    camera_id = uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/zones",
            json={
                "camera_id": str(camera_id),
                "name": "Entrance",
                "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
                "dwell_threshold_seconds": 5.0,
            },
        )
        zone_id = create_response.json()["id"]

        update_response = await client.patch(
            f"/zones/{zone_id}",
            json={"dwell_threshold_seconds": 12.0, "missing_object_threshold_seconds": 20.0},
        )

        assert update_response.status_code == 200
        assert update_response.json()["dwell_threshold_seconds"] == 12.0
        assert update_response.json()["missing_object_threshold_seconds"] == 20.0
        assert update_response.json()["name"] == "Entrance"


async def test_delete_zone_then_get_returns_404(tmp_path: Path) -> None:
    app = await _build_app(tmp_path / "zones.db")
    camera_id = uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/zones",
            json={
                "camera_id": str(camera_id),
                "name": "Entrance",
                "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
                "dwell_threshold_seconds": 5.0,
            },
        )
        zone_id = create_response.json()["id"]

        delete_response = await client.delete(f"/zones/{zone_id}")
        assert delete_response.status_code == 204

        get_response = await client.get(f"/zones/{zone_id}")
        assert get_response.status_code == 404


async def test_get_unknown_zone_returns_404(tmp_path: Path) -> None:
    app = await _build_app(tmp_path / "zones.db")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/zones/{uuid4()}")
        assert response.status_code == 404
