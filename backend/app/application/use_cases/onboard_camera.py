from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.camera import Camera


class OnboardCameraUseCase:
    """Authenticate against a camera over ONVIF and persist it with its stream profiles.

    Preconditions: `ip_address`/`username`/`password` identify a camera reachable
    on the network.

    Postconditions: a `Camera` (with its discovered `StreamProfile`s) is persisted
    via `camera_repository` and returned.

    Raises:
        CameraUnreachableError: the camera could not be reached or authentication failed.

    Real logic lands at M3 (docs/TASK_BACKLOG.md T-033); this milestone only
    establishes the signature and its dependency on the M1 ports.
    """

    def __init__(
        self, camera_gateway: ICameraGateway, camera_repository: ICameraRepository
    ) -> None:
        self._camera_gateway = camera_gateway
        self._camera_repository = camera_repository

    async def execute(self, ip_address: str, username: str, password: str) -> Camera:
        raise NotImplementedError
