from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, status

from app.application.use_cases.create_zone import CreateZoneUseCase
from app.application.use_cases.delete_zone import DeleteZoneUseCase
from app.application.use_cases.get_zone import GetZoneUseCase
from app.application.use_cases.list_zones_by_camera import ListZonesByCameraUseCase
from app.application.use_cases.update_zone import UpdateZoneUseCase
from app.interfaces.schemas.zones import ZoneCreateRequest, ZoneResponse, ZoneUpdateRequest


def create_zones_router(
    build_create_zone_use_case: Callable[[], CreateZoneUseCase],
    build_list_zones_by_camera_use_case: Callable[[], ListZonesByCameraUseCase],
    build_get_zone_use_case: Callable[[], GetZoneUseCase],
    build_update_zone_use_case: Callable[[], UpdateZoneUseCase],
    build_delete_zone_use_case: Callable[[], DeleteZoneUseCase],
) -> APIRouter:
    """Build the `/zones` router (T-111): `AnalyticsZone` polygon CRUD.

    A distinct resource/router from `analytics.py` (enable/disable + event
    listing), per `docs/FOLDER_STRUCTURE.md`'s "one router per resource"
    convention. Every use case is a stateless per-request factory (TD-08) —
    unlike `streams.py`/`analytics.py`'s singleton use cases, nothing here
    holds state across requests.
    """
    router = APIRouter(prefix="/zones", tags=["zones"])

    @router.post("", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
    async def create_zone(body: ZoneCreateRequest) -> ZoneResponse:
        zone = await build_create_zone_use_case().execute(
            camera_id=body.camera_id,
            name=body.name,
            polygon=body.polygon,
            dwell_threshold_seconds=body.dwell_threshold_seconds,
            missing_object_threshold_seconds=body.missing_object_threshold_seconds,
        )
        return ZoneResponse.from_domain(zone)

    @router.get("", response_model=list[ZoneResponse])
    async def list_zones(camera_id: UUID) -> list[ZoneResponse]:
        zones = await build_list_zones_by_camera_use_case().execute(camera_id)
        return [ZoneResponse.from_domain(zone) for zone in zones]

    @router.get("/{zone_id}", response_model=ZoneResponse)
    async def get_zone(zone_id: UUID) -> ZoneResponse:
        zone = await build_get_zone_use_case().execute(zone_id)
        return ZoneResponse.from_domain(zone)

    @router.patch("/{zone_id}", response_model=ZoneResponse)
    async def update_zone(zone_id: UUID, body: ZoneUpdateRequest) -> ZoneResponse:
        zone = await build_update_zone_use_case().execute(
            zone_id,
            name=body.name,
            polygon=body.polygon,
            dwell_threshold_seconds=body.dwell_threshold_seconds,
            missing_object_threshold_seconds=body.missing_object_threshold_seconds,
        )
        return ZoneResponse.from_domain(zone)

    @router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_zone(zone_id: UUID) -> None:
        await build_delete_zone_use_case().execute(zone_id)

    return router
