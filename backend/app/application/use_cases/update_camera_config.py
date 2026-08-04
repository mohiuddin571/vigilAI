from uuid import UUID

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.stream_profile import StreamProfile


class UpdateCameraConfigUseCase:
    """Update a camera's resolution/FPS/bitrate/codec for one stream profile.

    Preconditions: `camera_id` identifies a previously onboarded camera; the
    requested fields are ones the camera's own profile reports as configurable.

    Postconditions: the camera's encoder configuration is updated on the device
    and the persisted `Camera`/`StreamProfile` reflects the change.

    Raises:
        UnsupportedConfigurationError: the camera rejects the requested change.
        CameraUnreachableError: the camera could not be reached.

    Real logic lands at M4 (docs/TASK_BACKLOG.md T-040–T-042); this milestone
    only establishes the signature and its dependency on the M1 ports.
    """

    def __init__(
        self, camera_gateway: ICameraGateway, camera_repository: ICameraRepository
    ) -> None:
        self._camera_gateway = camera_gateway
        self._camera_repository = camera_repository

    async def execute(
        self, camera_id: UUID, profile_id: str, requested_profile: StreamProfile
    ) -> StreamProfile:
        raise NotImplementedError
