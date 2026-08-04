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
per-request use-case factories above). M5 adds `StartLiveStreamUseCase`,
built once and reused for the same reason (it holds a per-camera registry of
running Stream Workers across requests).
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
from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.application.use_cases.update_camera_rtsp_override import UpdateCameraRtspOverrideUseCase
from app.core.config import Settings
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource
from app.infrastructure.streaming.rtsp_frame_source import OnvifRtspFrameSource
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
        self._start_live_stream_use_case = StartLiveStreamUseCase(
            camera_gateway_factory=self.build_camera_gateway,
            camera_repository=self.build_camera_repository(),
            build_stream_worker=self._build_live_stream_worker,
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

    def build_update_camera_rtsp_override_use_case(self) -> UpdateCameraRtspOverrideUseCase:
        return UpdateCameraRtspOverrideUseCase(self.build_camera_repository())

    def _build_live_stream_worker(self, camera: Camera, profile: StreamProfile) -> StreamWorker:
        # Plain str/int args only (picklable), same `functools.partial` shape
        # as `_build_debug_stream_worker` — `OnvifRtspFrameSource` builds its
        # own `ICameraGateway` inside the child process via
        # `camera_gateway_factory` rather than receiving a live instance,
        # since `OnvifCameraGateway` itself isn't picklable (see
        # infrastructure/streaming/rtsp_frame_source.py).
        #
        # `profile.onvif_token` is guaranteed non-None here: this is only
        # ever called from `StartLiveStreamUseCase.execute()` with a profile
        # `_select_stream_profile` already validated has one.
        assert profile.onvif_token is not None
        frame_source_factory = functools.partial(
            OnvifRtspFrameSource,
            ip_address=camera.ip_address,
            username=camera.username,
            password=camera.password,
            rtsp_url_override=camera.rtsp_url_override,
            profile_id=profile.onvif_token,
            source_id=str(camera.id),
            camera_gateway_factory=OnvifCameraGateway,
            port=camera.port,
            open_timeout_ms=self._settings.rtsp_open_timeout_ms,
            read_timeout_ms=self._settings.rtsp_read_timeout_ms,
            rtsp_transport=self._settings.rtsp_transport,
        )
        return StreamWorker(
            frame_source_factory=frame_source_factory,
            backoff_schedule=self._settings.stream_worker_reconnect_backoff_seconds,
            frame_queue_max_size=self._settings.stream_worker_frame_queue_max_size,
        )

    def build_start_live_stream_use_case(self) -> StartLiveStreamUseCase:
        """Returns the single shared `StartLiveStreamUseCase` instance (T-050/T-052/T-053).

        Like `build_debug_stream_use_case`, this must be a singleton, not a
        per-request factory: it holds a registry of running Stream Workers
        keyed by `camera_id` across requests (start once, stream/poll status
        repeatedly, stop once).
        """
        return self._start_live_stream_use_case

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
