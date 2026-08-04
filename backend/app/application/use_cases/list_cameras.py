from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.camera import Camera


class ListCamerasUseCase:
    """Return every onboarded camera."""

    def __init__(self, camera_repository: ICameraRepository) -> None:
        self._camera_repository = camera_repository

    async def execute(self) -> list[Camera]:
        return await self._camera_repository.list()
