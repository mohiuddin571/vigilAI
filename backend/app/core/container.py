"""The composition root.

This is the one module in the project allowed to import across every layer
(domain, application, infrastructure, interfaces) — its entire job is to
build concrete adapters and inject them into use cases via plain constructor
arguments (TD-08: manual DI, not a framework, not FastAPI's `Depends`).

M3 adds the first concrete infrastructure adapters: `OnvifCameraGateway` and
`SqlCameraRepository`, wired into `OnboardCameraUseCase`/`ListCamerasUseCase`/
`GetCameraUseCase`. `OnvifCameraGateway` is built fresh on every call (see
`interfaces/api/cameras.py`'s router-factory docstring for why); the SQL
repository, its engine, and the credential cipher are built once and reused.
M4 wires the same two adapters into `GetCameraConfigUseCase`/
`UpdateCameraConfigUseCase`.
"""

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.get_camera import GetCameraUseCase
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.core.config import Settings
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher


class Container:
    """Holds the wired object graph for the application's lifetime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine = build_engine(settings.database_url)
        self._session_factory = build_session_factory(self._engine)
        self._cipher = CredentialCipher(settings.camera_credential_encryption_key)
        self._camera_repository: ICameraRepository = SqlCameraRepository(
            self._session_factory, self._cipher
        )

    async def init_db(self) -> None:
        await init_db(self._engine)

    def build_camera_gateway(self) -> ICameraGateway:
        return OnvifCameraGateway()

    def build_camera_repository(self) -> ICameraRepository:
        return self._camera_repository

    def build_onboard_camera_use_case(self) -> OnboardCameraUseCase:
        return OnboardCameraUseCase(self.build_camera_gateway(), self.build_camera_repository())

    def build_list_cameras_use_case(self) -> ListCamerasUseCase:
        return ListCamerasUseCase(self.build_camera_repository())

    def build_get_camera_use_case(self) -> GetCameraUseCase:
        return GetCameraUseCase(self.build_camera_repository())

    def build_get_camera_config_use_case(self) -> GetCameraConfigUseCase:
        return GetCameraConfigUseCase(self.build_camera_gateway(), self.build_camera_repository())

    def build_update_camera_config_use_case(self) -> UpdateCameraConfigUseCase:
        return UpdateCameraConfigUseCase(
            self.build_camera_gateway(), self.build_camera_repository()
        )
