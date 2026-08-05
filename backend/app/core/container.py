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
from uuid import UUID

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.ports.event_repository import IEventRepository
from app.application.ports.frame_source import IFrameSource
from app.application.ports.recording_repository import IRecordingRepository
from app.application.ports.recording_worker import IRecordingWorker
from app.application.use_cases.analytics_session_registry import AnalyticsSessionRegistry
from app.application.use_cases.debug_stream import DebugStreamUseCase
from app.application.use_cases.get_camera import GetCameraUseCase
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.get_recording import GetRecordingUseCase
from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.application.use_cases.list_detection_events import ListDetectionEventsUseCase
from app.application.use_cases.list_recordings import ListRecordingsUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.application.use_cases.run_analytics_pipeline import RunAnalyticsPipelineUseCase
from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.application.use_cases.start_recording import StartRecordingUseCase
from app.application.use_cases.stop_recording import StopRecordingUseCase
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.application.use_cases.update_camera_rtsp_override import UpdateCameraRtspOverrideUseCase
from app.core.config import Settings
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraNotFoundError, UnsupportedConfigurationError
from app.infrastructure.analytics.orchestrator import AnalyticsOrchestrator
from app.infrastructure.analytics.yolo_detector import YoloObjectDetector
from app.infrastructure.messaging.event_bus import EventBus
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.event_repository import SqlEventRepository
from app.infrastructure.persistence.recording_repository import SqlRecordingRepository
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.security.credential_cipher import CredentialCipher
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource
from app.infrastructure.streaming.recording_worker import FfmpegRecordingWorker
from app.infrastructure.streaming.rtsp_frame_source import OnvifRtspFrameSource
from app.infrastructure.streaming.stream_worker import StreamWorker
from app.infrastructure.streaming.supervised_frame_source import SupervisedFrameSource
from app.interfaces.websocket.analytics_events import AnalyticsEventsHub

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEBUG_MP4_FIXTURE_PATH = _REPO_ROOT / "backend" / "tests" / "fixtures" / "sample.mp4"
_ANALYTICS_MP4_SOURCE_ID = "mp4-demo"


def _select_primary_stream_profile(camera: Camera) -> StreamProfile:
    """Pick a stream profile to resolve a camera-backed analytics source from.

    A small, deliberate duplicate of `start_live_stream.py`'s private
    `_select_stream_profile`'s no-explicit-`profile_id` branch (M9,
    docs/TECHNICAL_DECISIONS.md TD-25) — importing a leading-underscore
    function across modules is worse than this ~10-line duplication, and
    analytics has no equivalent of live view's per-request `profile_id`
    override to justify reusing the fuller function.
    """
    for profile in camera.stream_profiles:
        if profile.is_primary and profile.onvif_token is not None:
            return profile
    for profile in camera.stream_profiles:
        if profile.onvif_token is not None:
            return profile
    raise UnsupportedConfigurationError(
        f"Camera {camera.id} has no stream profile with an ONVIF token to stream from"
    )


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
        self._recording_repository: IRecordingRepository = SqlRecordingRepository(
            self._session_factory
        )
        self._event_repository: IEventRepository = SqlEventRepository(self._session_factory)
        self._event_bus = EventBus()
        self._analytics_events_hub = AnalyticsEventsHub()
        self._event_bus.subscribe(self._event_repository.add)
        self._event_bus.subscribe(self._analytics_events_hub.broadcast)
        self._analytics_orchestrator = AnalyticsOrchestrator(
            [
                YoloObjectDetector(
                    model_path=str(settings.yolo_model_path),
                    confidence_threshold=settings.yolo_confidence_threshold,
                    iou_threshold=settings.yolo_iou_threshold,
                    device=settings.yolo_device,
                )
            ]
        )
        self._analytics_session_registry = AnalyticsSessionRegistry(
            build_use_case=self._build_analytics_use_case
        )
        self._debug_stream_use_case = DebugStreamUseCase(
            build_worker=self._build_debug_stream_worker
        )
        self._start_live_stream_use_case = StartLiveStreamUseCase(
            camera_gateway_factory=self.build_camera_gateway,
            camera_repository=self.build_camera_repository(),
            build_stream_worker=self._build_live_stream_worker,
        )
        self._recording_session_registry = RecordingSessionRegistry()
        self._start_recording_use_case = StartRecordingUseCase(
            camera_gateway_factory=self.build_camera_gateway,
            camera_repository=self.build_camera_repository(),
            recording_repository=self.build_recording_repository(),
            registry=self._recording_session_registry,
            build_recording_worker=self._build_recording_worker,
        )
        self._stop_recording_use_case = StopRecordingUseCase(
            recording_repository=self.build_recording_repository(),
            registry=self._recording_session_registry,
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

    def build_recording_repository(self) -> IRecordingRepository:
        return self._recording_repository

    def _build_recording_worker(self, camera_id: UUID, rtsp_url: str) -> IRecordingWorker:
        # No `multiprocessing`/picklability constraint here (unlike
        # `_build_live_stream_worker`): ffmpeg is already the isolated OS
        # process, so `rtsp_url` (resolved once by `StartRecordingUseCase`)
        # is passed straight through as a plain constructor argument.
        return FfmpegRecordingWorker(
            camera_id=camera_id,
            rtsp_url=rtsp_url,
            output_dir=self._settings.recording_output_dir,
            segment_duration_seconds=self._settings.recording_segment_duration_seconds,
            ffmpeg_binary_path=self._settings.ffmpeg_binary_path,
            ffprobe_binary_path=self._settings.ffprobe_binary_path,
        )

    def build_start_recording_use_case(self) -> StartRecordingUseCase:
        """Returns the single shared `StartRecordingUseCase` instance (T-062).

        Like `build_start_live_stream_use_case`, must be a singleton: it
        shares a `RecordingSessionRegistry` with `build_stop_recording_use_case`
        that tracks running ffmpeg subprocesses across requests.
        """
        return self._start_recording_use_case

    def build_stop_recording_use_case(self) -> StopRecordingUseCase:
        """Returns the single shared `StopRecordingUseCase` instance (T-062). See
        `build_start_recording_use_case`'s docstring for why."""
        return self._stop_recording_use_case

    def build_list_recordings_use_case(self) -> ListRecordingsUseCase:
        return ListRecordingsUseCase(self.build_recording_repository())

    def build_get_recording_use_case(self) -> GetRecordingUseCase:
        return GetRecordingUseCase(self.build_recording_repository())

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

    async def _build_analytics_frame_source(self, source_id: str) -> IFrameSource:
        # M9 (docs/TECHNICAL_DECISIONS.md TD-25) widens M8's "mp4-demo"-only
        # source to also accept a real onboarded camera's id, resolved the
        # same way `_build_live_stream_worker` resolves one for live view —
        # wrapped in `SupervisedFrameSource` either way, so consumption goes
        # through the same `ReconnectSupervisor` reconnect/backoff path M5's
        # live-view and M6's recording already build on (docs/IMPLEMENTATION_PLAN.md
        # §M8's Constraints, unchanged by this milestone).
        if source_id == _ANALYTICS_MP4_SOURCE_ID:
            source: IFrameSource = Mp4FileFrameSource(
                file_path=str(_DEBUG_MP4_FIXTURE_PATH), source_id=source_id
            )
        else:
            source = await self._build_camera_analytics_source(source_id)
        return SupervisedFrameSource(
            source, backoff_schedule=self._settings.stream_worker_reconnect_backoff_seconds
        )

    async def _build_camera_analytics_source(self, source_id: str) -> IFrameSource:
        try:
            camera_id = UUID(source_id)
        except ValueError as exc:
            raise UnsupportedConfigurationError(
                f"No analytics-enableable source {source_id!r}"
                f" (expected {_ANALYTICS_MP4_SOURCE_ID!r} or an onboarded camera id)"
            ) from exc
        camera = await self._camera_repository.get(camera_id)
        if camera is None:
            raise CameraNotFoundError(f"No onboarded camera with id {camera_id}")
        profile = _select_primary_stream_profile(camera)
        assert profile.onvif_token is not None
        return OnvifRtspFrameSource(
            ip_address=camera.ip_address,
            username=camera.username,
            password=camera.password,
            rtsp_url_override=camera.rtsp_url_override,
            profile_id=profile.onvif_token,
            source_id=str(camera.id),
            camera_gateway_factory=self.build_camera_gateway,
            port=camera.port,
            open_timeout_ms=self._settings.rtsp_open_timeout_ms,
            read_timeout_ms=self._settings.rtsp_read_timeout_ms,
            rtsp_transport=self._settings.rtsp_transport,
        )

    async def _build_analytics_use_case(self, source_id: str) -> RunAnalyticsPipelineUseCase:
        return RunAnalyticsPipelineUseCase(
            frame_source=await self._build_analytics_frame_source(source_id),
            process_frame=self._analytics_orchestrator.process,
            event_publisher=self._event_bus,
        )

    def build_analytics_session_registry(self) -> AnalyticsSessionRegistry:
        """Returns the single shared `AnalyticsSessionRegistry` instance (T-085).

        Like `build_start_live_stream_use_case`, must be a singleton: it
        holds running analytics sessions keyed by `source_id` across requests.
        """
        return self._analytics_session_registry

    def build_list_detection_events_use_case(self) -> ListDetectionEventsUseCase:
        return ListDetectionEventsUseCase(self._event_repository)

    def build_analytics_events_hub(self) -> AnalyticsEventsHub:
        return self._analytics_events_hub
