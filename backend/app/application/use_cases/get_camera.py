from uuid import UUID

from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.camera import Camera
from app.domain.exceptions import CameraNotFoundError


class GetCameraUseCase:
    """Return a single onboarded camera by id.

    Raises:
        CameraNotFoundError: no camera exists for the given id.
    """

    def __init__(self, camera_repository: ICameraRepository) -> None:
        self._camera_repository = camera_repository

    async def execute(self, camera_id: UUID) -> Camera:
        camera = await self._camera_repository.get(camera_id)
        if camera is None:
            raise CameraNotFoundError(f"No camera with id {camera_id}")
        return camera
