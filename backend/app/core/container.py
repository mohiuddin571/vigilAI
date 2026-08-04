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

M2 adds `DebugStreamUseCase`, built once and reused (see
`build_debug_stream_use_case`'s docstring for why this one differs from the
per-request use-case factories above).
"""

import functools
from pathlib import Path

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.debug_stream import DebugStreamUseCase
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
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource
from app.infrastructure.streaming.stream_worker import StreamWorker

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEBUG_MP4_FIXTURE_PATH = _REPO_ROOT / "backend" / "tests" / "fixtures" / "sample.mp4"


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
        self._debug_stream_use_case = DebugStreamUseCase(
            build_worker=self._build_debug_stream_worker
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

    def _build_debug_stream_worker(self) -> StreamWorker:
        # A `functools.partial` over a module-level class with plain
        # str/bool args (not a lambda/closure) — it must survive a pickle
        # round-trip to cross the `multiprocessing` "spawn" boundary
        # `StreamWorker` uses (see infrastructure/streaming/stream_worker.py).
        frame_source_factory = functools.partial(
            Mp4FileFrameSource,
            file_path=str(_DEBUG_MP4_FIXTURE_PATH),
            source_id="debug-mp4",
            loop=True,
        )
        return StreamWorker(
            frame_source_factory=frame_source_factory,
            backoff_schedule=self._settings.stream_worker_reconnect_backoff_seconds,
            frame_queue_max_size=self._settings.stream_worker_frame_queue_max_size,
        )

    def build_debug_stream_use_case(self) -> DebugStreamUseCase:
        """Returns the single shared `DebugStreamUseCase` instance (T-025).

        Unlike `build_onboard_camera_use_case` et al., this is *not* a
        per-request factory: its whole purpose is to hold one running Stream
        Worker across requests (start once, poll status repeatedly, stop
        once), so the same instance must be returned every call.
        """
        return self._debug_stream_use_case
