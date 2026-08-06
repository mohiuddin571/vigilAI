from uuid import UUID, uuid4

import pytest

from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.update_camera import UpdateCameraUseCase
from app.domain.entities.camera import Camera
from app.domain.exceptions import CameraNotFoundError, InvalidDomainStateError


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

    async def delete(self, camera_id: UUID) -> None:
        self.cameras.pop(camera_id, None)


def _make_camera(**overrides: object) -> Camera:
    defaults: dict[str, object] = {
        "name": "Front Door",
        "ip_address": "10.0.0.5",
        "username": "admin",
    }
    defaults.update(overrides)
    return Camera(**defaults)  # type: ignore[arg-type]


async def test_update_camera_applies_only_provided_fields() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraUseCase(repository)

    updated = await use_case.execute(camera.id, name="Back Door")

    assert updated.name == "Back Door"
    assert updated.ip_address == "10.0.0.5"
    assert updated.username == "admin"
    assert repository.cameras[camera.id].name == "Back Door"


async def test_update_camera_updates_ip_port_username_password() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraUseCase(repository)

    updated = await use_case.execute(
        camera.id, ip_address="10.0.0.9", port=8080, username="operator", password="new-secret"
    )

    assert updated.ip_address == "10.0.0.9"
    assert updated.port == 8080
    assert updated.username == "operator"
    assert updated.password == "new-secret"


async def test_update_camera_preserves_id_and_untouched_fields() -> None:
    camera = _make_camera(manufacturer="Acme", model="X100", is_online=True)
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraUseCase(repository)

    updated = await use_case.execute(camera.id, name="Renamed")

    assert updated.id == camera.id
    assert updated.manufacturer == "Acme"
    assert updated.model == "X100"
    assert updated.is_online is True


async def test_update_camera_preserves_enabled_detector_types() -> None:
    camera = _make_camera(enabled_detector_types=frozenset({"color_detector"}))
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraUseCase(repository)

    updated = await use_case.execute(camera.id, name="Renamed")

    assert updated.enabled_detector_types == frozenset({"color_detector"})


async def test_update_camera_raises_not_found_for_unknown_id() -> None:
    use_case = UpdateCameraUseCase(FakeCameraRepository())

    with pytest.raises(CameraNotFoundError):
        await use_case.execute(uuid4(), name="New name")


async def test_update_camera_rejects_empty_name_via_domain_validation() -> None:
    camera = _make_camera()
    use_case = UpdateCameraUseCase(FakeCameraRepository([camera]))

    with pytest.raises(InvalidDomainStateError):
        await use_case.execute(camera.id, name="   ")


async def test_update_camera_rejects_invalid_ip_via_domain_validation() -> None:
    camera = _make_camera()
    use_case = UpdateCameraUseCase(FakeCameraRepository([camera]))

    with pytest.raises(InvalidDomainStateError):
        await use_case.execute(camera.id, ip_address="not-an-ip")
