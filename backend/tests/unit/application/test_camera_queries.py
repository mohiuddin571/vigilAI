from uuid import UUID, uuid4

import pytest

from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.get_camera import GetCameraUseCase
from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.domain.entities.camera import Camera
from app.domain.exceptions import CameraNotFoundError


class FakeCameraRepository(ICameraRepository):
    def __init__(self, cameras: list[Camera] | None = None) -> None:
        self.cameras: dict[UUID, Camera] = {camera.id: camera for camera in cameras or []}

    async def add(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera

    async def get(self, camera_id: UUID) -> Camera | None:
        return self.cameras.get(camera_id)

    async def list(self) -> list[Camera]:
        return list(self.cameras.values())

    async def update(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera


async def test_list_cameras_returns_every_persisted_camera() -> None:
    camera = Camera(name="Front Door", ip_address="10.0.0.5", username="admin")
    use_case = ListCamerasUseCase(FakeCameraRepository([camera]))

    result = await use_case.execute()

    assert result == [camera]


async def test_get_camera_returns_matching_camera() -> None:
    camera = Camera(name="Front Door", ip_address="10.0.0.5", username="admin")
    use_case = GetCameraUseCase(FakeCameraRepository([camera]))

    result = await use_case.execute(camera.id)

    assert result is camera


async def test_get_camera_raises_not_found_for_unknown_id() -> None:
    use_case = GetCameraUseCase(FakeCameraRepository())

    with pytest.raises(CameraNotFoundError):
        await use_case.execute(uuid4())
