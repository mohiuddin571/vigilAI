from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, status

from app.application.use_cases.get_camera import GetCameraUseCase
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.application.use_cases.update_camera_rtsp_override import UpdateCameraRtspOverrideUseCase
from app.interfaces.schemas.camera import (
    CameraConfigResponse,
    CameraConfigUpdateRequest,
    CameraCreateRequest,
    CameraResponse,
    CameraRtspOverrideRequest,
)


def create_cameras_router(
    build_onboard_camera_use_case: Callable[[], OnboardCameraUseCase],
    build_list_cameras_use_case: Callable[[], ListCamerasUseCase],
    build_get_camera_use_case: Callable[[], GetCameraUseCase],
    build_get_camera_config_use_case: Callable[[], GetCameraConfigUseCase],
    build_update_camera_config_use_case: Callable[[], UpdateCameraConfigUseCase],
    build_update_camera_rtsp_override_use_case: (
        Callable[[], UpdateCameraRtspOverrideUseCase] | None
    ) = None,
) -> APIRouter:
    """Build the `/cameras` router from use-case factories supplied by the composition root.

    A factory (not an already-built instance) per TD-08: `OnboardCameraUseCase`
    holds an `OnvifCameraGateway` with per-connection mutable state, so a fresh
    instance is needed for every request — building it once at startup would
    let concurrent onboarding requests corrupt each other's ONVIF session.
    FastAPI's `Depends` is deliberately not used here (TD-02: reserved for
    request-scoped concerns, not this project's DI mechanism).
    """
    router = APIRouter(prefix="/cameras", tags=["cameras"])

    @router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
    async def onboard_camera(body: CameraCreateRequest) -> CameraResponse:
        camera = await build_onboard_camera_use_case().execute(
            ip_address=body.ip_address,
            username=body.username,
            password=body.password,
            port=body.port,
            rtsp_url_override=body.rtsp_url_override,
        )
        return CameraResponse.from_domain(camera)

    @router.get("", response_model=list[CameraResponse])
    async def list_cameras() -> list[CameraResponse]:
        cameras = await build_list_cameras_use_case().execute()
        return [CameraResponse.from_domain(camera) for camera in cameras]

    @router.get("/{camera_id}", response_model=CameraResponse)
    async def get_camera(camera_id: UUID) -> CameraResponse:
        camera = await build_get_camera_use_case().execute(camera_id)
        return CameraResponse.from_domain(camera)

    @router.get("/{camera_id}/config", response_model=CameraConfigResponse)
    async def get_camera_config(camera_id: UUID, profile_id: str) -> CameraConfigResponse:
        dto = await build_get_camera_config_use_case().execute(camera_id, profile_id)
        return CameraConfigResponse.from_dto(dto)

    @router.patch("/{camera_id}/config", response_model=CameraConfigResponse)
    async def update_camera_config(
        camera_id: UUID, profile_id: str, body: CameraConfigUpdateRequest
    ) -> CameraConfigResponse:
        profile = await build_update_camera_config_use_case().execute(
            camera_id, profile_id, body.to_dto()
        )
        return CameraConfigResponse.from_profile(profile)

    if build_update_camera_rtsp_override_use_case is not None:

        @router.patch("/{camera_id}/rtsp-url", response_model=CameraResponse)
        async def update_camera_rtsp_url(
            camera_id: UUID, body: CameraRtspOverrideRequest
        ) -> CameraResponse:
            camera = await build_update_camera_rtsp_override_use_case().execute(
                camera_id, body.rtsp_url_override
            )
            return CameraResponse.from_domain(camera)

    return router
