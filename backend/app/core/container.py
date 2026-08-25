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

import structlog

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.ports.demo_video_repository import IDemoVideoRepository
from app.application.ports.detector_plugin import IDetectorPlugin
from app.application.ports.event_repository import IEventRepository
from app.application.ports.frame_source import IFrameSource
from app.application.ports.recording_file_store import IRecordingFileStore
from app.application.ports.recording_repository import IRecordingRepository
from app.application.ports.recording_worker import IRecordingWorker
from app.application.ports.rtmp_publisher import IRtmpPublisher
from app.application.ports.rtmp_server_controller import IRtmpServerController
from app.application.use_cases.analytics_session_registry import AnalyticsSessionRegistry
from app.application.use_cases.clear_detection_events import ClearDetectionEventsUseCase
from app.application.use_cases.create_zone import CreateZoneUseCase
from app.application.use_cases.debug_stream import DebugStreamUseCase
from app.application.use_cases.delete_camera import DeleteCameraUseCase
from app.application.use_cases.delete_recording import DeleteRecordingUseCase
from app.application.use_cases.delete_zone import DeleteZoneUseCase
from app.application.use_cases.get_camera import GetCameraUseCase
from app.application.use_cases.get_camera_config import GetCameraConfigUseCase
from app.application.use_cases.get_recording import GetRecordingUseCase
from app.application.use_cases.get_zone import GetZoneUseCase
from app.application.use_cases.list_cameras import ListCamerasUseCase
from app.application.use_cases.list_demo_videos import ListDemoVideosUseCase
from app.application.use_cases.list_detection_events import ListDetectionEventsUseCase
from app.application.use_cases.list_recordings import ListRecordingsUseCase
from app.application.use_cases.list_zones_by_camera import ListZonesByCameraUseCase
from app.application.use_cases.manage_rtmp_publisher import ManageRtmpPublisherUseCase
from app.application.use_cases.manage_rtmp_server import ManageRtmpServerUseCase
from app.application.use_cases.onboard_camera import OnboardCameraUseCase
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.application.use_cases.run_analytics_pipeline import RunAnalyticsPipelineUseCase
from app.application.use_cases.start_demo_stream import StartDemoStreamUseCase
from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.application.use_cases.start_recording import StartRecordingUseCase
from app.application.use_cases.start_rtmp_consumer import StartRtmpConsumerUseCase
from app.application.use_cases.stop_recording import StopRecordingUseCase
from app.application.use_cases.update_camera import UpdateCameraUseCase
from app.application.use_cases.update_camera_analytics_settings import (
    UpdateCameraAnalyticsSettingsUseCase,
)
from app.application.use_cases.update_camera_config import UpdateCameraConfigUseCase
from app.application.use_cases.update_camera_rtsp_override import UpdateCameraRtspOverrideUseCase
from app.application.use_cases.update_zone import UpdateZoneUseCase
from app.core.config import Settings
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraNotFoundError, UnsupportedConfigurationError
from app.infrastructure.analytics.color_detector import ColorDetector
from app.infrastructure.analytics.easyocr_reader import EasyOcrReader
from app.infrastructure.analytics.license_plate_recognizer import LicensePlateRecognizer
from app.infrastructure.analytics.loitering_detector import LoiteringDetector
from app.infrastructure.analytics.missing_object_detector import MissingObjectDetector
from app.infrastructure.analytics.orchestrator import AnalyticsOrchestrator
from app.infrastructure.analytics.plate_localizer import PlateLocalizer
from app.infrastructure.analytics.yolo_detector import YoloObjectDetector
from app.infrastructure.messaging.event_bus import EventBus
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.persistence.analytics_zone_repository import SqlAnalyticsZoneRepository
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.event_repository import SqlEventRepository
from app.infrastructure.persistence.recording_repository import SqlRecordingRepository
from app.infrastructure.persistence.sql_camera_repository import SqlCameraRepository
from app.infrastructure.rtmp_demo.ffmpeg_publisher import FfmpegRtmpPublisher, build_rtmp_url
from app.infrastructure.rtmp_demo.mediamtx_server import MediaMtxServerController
from app.infrastructure.rtmp_demo.rtmp_frame_source import RtmpFrameSource
from app.infrastructure.security.credential_cipher import CredentialCipher
from app.infrastructure.streaming.local_demo_video_repository import LocalDemoVideoRepository
from app.infrastructure.streaming.local_recording_file_store import LocalRecordingFileStore
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource
from app.infrastructure.streaming.recording_worker import FfmpegRecordingWorker
from app.infrastructure.streaming.rtsp_frame_source import OnvifRtspFrameSource
from app.infrastructure.streaming.stream_worker import StreamWorker
from app.infrastructure.streaming.supervised_frame_source import SupervisedFrameSource
from app.interfaces.websocket.analytics_events import AnalyticsEventsHub

logger = structlog.get_logger(__name__)

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
        self._recording_file_store: IRecordingFileStore = LocalRecordingFileStore()
        self._event_repository: IEventRepository = SqlEventRepository(self._session_factory)
        self._zone_repository: IAnalyticsZoneRepository = SqlAnalyticsZoneRepository(
            self._session_factory
        )
        self._event_bus = EventBus()
        self._analytics_events_hub = AnalyticsEventsHub()
        self._event_bus.subscribe(self._event_repository.add)
        self._event_bus.subscribe(self._analytics_events_hub.broadcast)
        detector_plugins: list[IDetectorPlugin] = [
            # Order matters: ColorDetector, LoiteringDetector, and
            # MissingObjectDetector all read the bounding boxes/track ids
            # YoloObjectDetector writes into `context` for this same frame
            # (T-100/T-113/T-121, docs/TECHNICAL_DECISIONS.md
            # TD-27/TD-28/TD-29) — all three must run after
            # YoloObjectDetector in this list. LicensePlateRecognizer
            # (T-132, TD-30) is the one exception: it localizes plate
            # candidates over the full frame independently, reading
            # nothing from `context` — its position in this list is
            # therefore not order-dependent, kept last for readability.
            YoloObjectDetector(
                model_path=str(settings.yolo_model_path),
                confidence_threshold=settings.yolo_confidence_threshold,
                iou_threshold=settings.yolo_iou_threshold,
                device=settings.yolo_device,
            ),
            ColorDetector(),
            LoiteringDetector(zone_repository=self._zone_repository),
            MissingObjectDetector(zone_repository=self._zone_repository),
            LicensePlateRecognizer(
                plate_localizer=PlateLocalizer(),
                plate_reader=EasyOcrReader(
                    languages=settings.easyocr_languages,
                    model_storage_directory=str(settings.easyocr_model_storage_dir),
                    gpu=settings.easyocr_gpu,
                    min_confidence=settings.easyocr_min_confidence,
                ),
                queue_max_size=settings.lpr_ocr_queue_max_size,
            ),
        ]
        # Kept alongside the orchestrator (not read back off it) so the
        # per-camera Settings tab (`UpdateCameraAnalyticsSettingsUseCase`,
        # `/cameras/{id}/analytics-settings`) has a single source of truth for
        # which `plugin_id`s are valid to enable/disable, without reaching
        # into `AnalyticsOrchestrator`'s private plugin list.
        self._known_detector_types: frozenset[str] = frozenset(
            plugin.plugin_id for plugin in detector_plugins
        )
        self._analytics_orchestrator = AnalyticsOrchestrator(detector_plugins)
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
        self._demo_video_repository: IDemoVideoRepository = LocalDemoVideoRepository(
            settings.demo_videos_dir
        )
        self._start_demo_stream_use_case = StartDemoStreamUseCase(
            demo_video_repository=self._demo_video_repository,
            build_stream_worker=self._build_demo_stream_worker,
        )
        # RTMP Push/Consume Demo (docs/RTMP_DEMO.md) — isolated, outside the
        # graded milestone sequence. Three independent lifecycles (server,
        # publisher, consumer), each a shared singleton for the same reason
        # `_start_live_stream_use_case`/`_start_demo_stream_use_case` are:
        # they hold a running subprocess/Stream Worker across requests.
        self._rtmp_server_controller: IRtmpServerController = MediaMtxServerController(
            settings.mediamtx_binary_path,
            settings.rtmp_demo_runtime_dir,
            host=settings.rtmp_server_host,
            port=settings.rtmp_server_port,
            app_name=settings.rtmp_app_name,
            stream_key=settings.rtmp_stream_key,
            publish_username=settings.rtmp_publish_username,
            publish_password=settings.rtmp_publish_password,
            read_username=settings.rtmp_read_username,
            read_password=settings.rtmp_read_password,
        )
        self._manage_rtmp_server_use_case = ManageRtmpServerUseCase(self._rtmp_server_controller)
        self._rtmp_publisher: IRtmpPublisher = FfmpegRtmpPublisher(
            settings.ffmpeg_binary_path,
            host=settings.rtmp_server_host,
            port=settings.rtmp_server_port,
            app_name=settings.rtmp_app_name,
            stream_key=settings.rtmp_stream_key,
            publish_username=settings.rtmp_publish_username,
            publish_password=settings.rtmp_publish_password,
            video_bitrate_kbps=settings.rtmp_publish_video_bitrate_kbps,
            resolution=settings.rtmp_publish_resolution,
            fps=settings.rtmp_publish_fps,
        )
        self._manage_rtmp_publisher_use_case = ManageRtmpPublisherUseCase(
            self._rtmp_publisher, self._demo_video_repository
        )
        self._start_rtmp_consumer_use_case = StartRtmpConsumerUseCase(
            build_stream_worker=self._build_rtmp_consumer_stream_worker
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

    async def shutdown(self) -> None:
        """Stop every subprocess-backed worker this process owns.

        Called from `main.py`'s lifespan on a graceful shutdown (Ctrl+C /
        `SIGTERM` / a plain `kill`) so restarting the dev server never
        orphans a Stream Worker (`multiprocessing.Process`, live view + the
        debug MP4 stream) or a Recording Worker (`ffmpeg` via
        `asyncio.create_subprocess_exec`) — both leaked repeatedly during a
        real debugging session where the server was instead `kill -9`'d,
        which bypasses this path entirely (SIGKILL allows no Python code,
        including this method, to run) and accumulated over a dozen orphaned
        processes competing with real streams for CPU. `daemon=True` on
        `StreamWorker`'s child process already gives *some* protection on a
        clean exit via Python's own `atexit` handling, but that's implicit
        and doesn't cover the `ffmpeg` subprocess case at all — this makes
        cleanup explicit, logged, and complete for both.
        """
        logger.info("container.shutdown_started")
        await self._debug_stream_use_case.stop()
        await self._start_live_stream_use_case.stop_all()
        await self._start_demo_stream_use_case.stop_all()
        # Consumer, then publisher, then server — release the RTMP demo's
        # subprocesses in the reverse order they'd naturally be started in.
        await self._start_rtmp_consumer_use_case.stop_all()
        await self._manage_rtmp_publisher_use_case.stop()
        await self._manage_rtmp_server_use_case.stop()
        stop_recording = self.build_stop_recording_use_case()
        for camera_id in self._recording_session_registry.active_camera_ids():
            try:
                await stop_recording.execute(camera_id)
            except Exception:
                logger.exception("container.shutdown_recording_stop_failed", camera_id=camera_id)
        logger.info("container.shutdown_complete")

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

    def build_update_camera_use_case(self) -> UpdateCameraUseCase:
        return UpdateCameraUseCase(self.build_camera_repository())

    def build_recording_file_store(self) -> IRecordingFileStore:
        return self._recording_file_store

    def build_delete_recording_use_case(self) -> DeleteRecordingUseCase:
        return DeleteRecordingUseCase(
            self.build_recording_repository(), self.build_recording_file_store()
        )

    def build_delete_camera_use_case(self) -> DeleteCameraUseCase:
        """A per-request factory (unlike `build_start_live_stream_use_case` et al.'s
        singletons) — it only orchestrates other already-shared singletons
        (`_start_live_stream_use_case`, `_stop_recording_use_case`,
        `_analytics_session_registry`) rather than holding any state of its own."""
        return DeleteCameraUseCase(
            camera_repository=self.build_camera_repository(),
            zone_repository=self.build_zone_repository(),
            recording_repository=self.build_recording_repository(),
            delete_recording_use_case=self.build_delete_recording_use_case(),
            event_repository=self._event_repository,
            stream_use_case=self.build_start_live_stream_use_case(),
            stop_recording_use_case=self.build_stop_recording_use_case(),
            analytics_registry=self.build_analytics_session_registry(),
        )

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

    def _build_demo_stream_worker(self, video_id: str, file_path: Path) -> StreamWorker:
        # Same `functools.partial`-over-a-module-level-class shape as
        # `_build_debug_stream_worker`/`_build_live_stream_worker` (picklable
        # plain str args only, for the `multiprocessing` spawn boundary).
        frame_source_factory = functools.partial(
            Mp4FileFrameSource,
            file_path=str(file_path),
            source_id=video_id,
            loop=True,
        )
        return StreamWorker(
            frame_source_factory=frame_source_factory,
            backoff_schedule=self._settings.stream_worker_reconnect_backoff_seconds,
            frame_queue_max_size=self._settings.stream_worker_frame_queue_max_size,
        )

    def build_list_demo_videos_use_case(self) -> ListDemoVideosUseCase:
        return ListDemoVideosUseCase(self._demo_video_repository)

    def build_start_demo_stream_use_case(self) -> StartDemoStreamUseCase:
        """Returns the single shared `StartDemoStreamUseCase` instance (M17), for the
        same reason as `build_start_live_stream_use_case`: it holds a registry of
        running demo Stream Workers across requests."""
        return self._start_demo_stream_use_case

    def build_manage_rtmp_server_use_case(self) -> ManageRtmpServerUseCase:
        """Returns the single shared `ManageRtmpServerUseCase` instance (docs/RTMP_DEMO.md), for
        the same reason as `build_start_live_stream_use_case`: it holds the running MediaMTX
        subprocess across requests."""
        return self._manage_rtmp_server_use_case

    def build_manage_rtmp_publisher_use_case(self) -> ManageRtmpPublisherUseCase:
        """Returns the single shared `ManageRtmpPublisherUseCase` instance (docs/RTMP_DEMO.md),
        for the same reason as `build_manage_rtmp_server_use_case`: it holds the running ffmpeg
        publisher subprocess across requests."""
        return self._manage_rtmp_publisher_use_case

    def _build_rtmp_consumer_stream_worker(self) -> StreamWorker:
        # Same `functools.partial`-over-a-module-level-class shape as
        # `_build_demo_stream_worker` (picklable plain str/int args only, for
        # the `multiprocessing` spawn boundary `StreamWorker` uses). The
        # consumer always reads with the *read* credentials (if configured),
        # independent of whichever publish credentials the publisher used.
        rtmp_url = build_rtmp_url(
            self._settings.rtmp_server_host,
            self._settings.rtmp_server_port,
            self._settings.rtmp_app_name,
            self._settings.rtmp_stream_key,
            self._settings.rtmp_read_username,
            self._settings.rtmp_read_password,
        )
        frame_source_factory = functools.partial(
            RtmpFrameSource,
            rtmp_url=rtmp_url,
            source_id="rtmp-demo-consumer",
            open_timeout_ms=self._settings.rtmp_open_timeout_ms,
            read_timeout_ms=self._settings.rtmp_read_timeout_ms,
        )
        return StreamWorker(
            frame_source_factory=frame_source_factory,
            backoff_schedule=self._settings.stream_worker_reconnect_backoff_seconds,
            frame_queue_max_size=self._settings.stream_worker_frame_queue_max_size,
        )

    def build_start_rtmp_consumer_use_case(self) -> StartRtmpConsumerUseCase:
        """Returns the single shared `StartRtmpConsumerUseCase` instance (docs/RTMP_DEMO.md), for
        the same reason as `build_manage_rtmp_server_use_case`: it holds the running consumer
        Stream Worker across requests."""
        return self._start_rtmp_consumer_use_case

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
        # same way `_build_live_stream_worker` resolves one for live view.
        # M17 adds a third branch for the demo video library, checked before
        # the camera-UUID fallback since a demo video's `source_id` is a
        # filename-derived slug, never a UUID — wrapped in
        # `SupervisedFrameSource` in every branch, so consumption goes
        # through the same `ReconnectSupervisor` reconnect/backoff path M5's
        # live-view and M6's recording already build on (docs/IMPLEMENTATION_PLAN.md
        # §M8's Constraints, unchanged by this milestone).
        demo_video_path = self._demo_video_repository.resolve_path(source_id)
        if source_id == _ANALYTICS_MP4_SOURCE_ID:
            source: IFrameSource = Mp4FileFrameSource(
                file_path=str(_DEBUG_MP4_FIXTURE_PATH), source_id=source_id
            )
        elif demo_video_path is not None:
            source = Mp4FileFrameSource(file_path=str(demo_video_path), source_id=source_id)
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
        enabled_plugin_ids = await self._resolve_enabled_detector_types(source_id)
        return RunAnalyticsPipelineUseCase(
            frame_source=await self._build_analytics_frame_source(source_id),
            process_frame=functools.partial(
                self._analytics_orchestrator.process, enabled_plugin_ids=enabled_plugin_ids
            ),
            event_publisher=self._event_bus,
        )

    async def _resolve_enabled_detector_types(self, source_id: str) -> frozenset[str] | None:
        """This source's `Camera.enabled_detector_types`, or `None` for the debug
        MP4 stream/an id that doesn't resolve to an onboarded camera.

        Deliberately best-effort, unlike `_build_camera_analytics_source`
        (which raises `UnsupportedConfigurationError`/`CameraNotFoundError`
        for the same bad-id cases): resolving settings is not the place that
        should block analytics from starting for a source that's otherwise
        fine — that method is still the one that raises for a genuinely
        invalid `source_id`, so an unresolvable id here just falls back to
        "no camera-specific settings" (all plugins enabled) rather than
        duplicating that error handling.
        """
        try:
            camera_id = UUID(source_id)
        except ValueError:
            return None
        camera = await self._camera_repository.get(camera_id)
        return camera.enabled_detector_types if camera is not None else None

    @property
    def known_detector_types(self) -> frozenset[str]:
        return self._known_detector_types

    def build_update_camera_analytics_settings_use_case(
        self,
    ) -> UpdateCameraAnalyticsSettingsUseCase:
        return UpdateCameraAnalyticsSettingsUseCase(
            self.build_camera_repository(),
            known_detector_types=self._known_detector_types,
            analytics_session_registry=self._analytics_session_registry,
        )

    def build_analytics_session_registry(self) -> AnalyticsSessionRegistry:
        """Returns the single shared `AnalyticsSessionRegistry` instance (T-085).

        Like `build_start_live_stream_use_case`, must be a singleton: it
        holds running analytics sessions keyed by `source_id` across requests.
        """
        return self._analytics_session_registry

    def build_list_detection_events_use_case(self) -> ListDetectionEventsUseCase:
        return ListDetectionEventsUseCase(self._event_repository)

    def build_clear_detection_events_use_case(self) -> ClearDetectionEventsUseCase:
        return ClearDetectionEventsUseCase(self._event_repository)

    def build_analytics_events_hub(self) -> AnalyticsEventsHub:
        return self._analytics_events_hub

    def build_zone_repository(self) -> IAnalyticsZoneRepository:
        return self._zone_repository

    def build_create_zone_use_case(self) -> CreateZoneUseCase:
        return CreateZoneUseCase(self.build_zone_repository())

    def build_list_zones_by_camera_use_case(self) -> ListZonesByCameraUseCase:
        return ListZonesByCameraUseCase(self.build_zone_repository())

    def build_get_zone_use_case(self) -> GetZoneUseCase:
        return GetZoneUseCase(self.build_zone_repository())

    def build_update_zone_use_case(self) -> UpdateZoneUseCase:
        return UpdateZoneUseCase(self.build_zone_repository())

    def build_delete_zone_use_case(self) -> DeleteZoneUseCase:
        return DeleteZoneUseCase(self.build_zone_repository())
