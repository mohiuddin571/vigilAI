from uuid import UUID

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository


class StartLiveStreamUseCase:
    """Resolve a camera's stream URI and start a Stream Worker producing frames from it.

    Preconditions: `camera_id` identifies a previously onboarded, reachable camera.

    Postconditions: a Stream Worker is running for the camera and frames are
    available for live-view/analytics consumers.

    Raises:
        CameraUnreachableError: the camera could not be reached to resolve a stream URI.

    Real logic lands at M5 (docs/TASK_BACKLOG.md T-050); this milestone only
    establishes the signature and its dependency on the M1 ports.
    """

    def __init__(
        self, camera_gateway: ICameraGateway, camera_repository: ICameraRepository
    ) -> None:
        self._camera_gateway = camera_gateway
        self._camera_repository = camera_repository

    async def execute(self, camera_id: UUID) -> None:
        raise NotImplementedError
