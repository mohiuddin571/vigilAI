from uuid import UUID

from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.camera import Camera
from app.domain.exceptions import CameraNotFoundError


class UpdateCameraRtspOverrideUseCase:
    """Persist the public RTSP endpoint used when ONVIF reports an unusable one."""

    def __init__(self, camera_repository: ICameraRepository) -> None:
        self._camera_repository = camera_repository

    async def execute(self, camera_id: UUID, rtsp_url_override: str | None) -> Camera:
        camera = await self._camera_repository.get(camera_id)
        if camera is None:
            raise CameraNotFoundError(f"No camera with id {camera_id}")
        camera.rtsp_url_override = rtsp_url_override
        await self._camera_repository.update(camera)
        return camera
