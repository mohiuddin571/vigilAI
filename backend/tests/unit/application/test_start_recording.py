from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.ports.recording_repository import IRecordingRepository
from app.application.ports.recording_worker import IRecordingWorker
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.application.use_cases.start_recording import StartRecordingUseCase
from app.domain.entities.camera import Camera
from app.domain.entities.recording import Recording
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import (
    CameraAuthenticationError,
    CameraNotFoundError,
    UnsupportedConfigurationError,
)
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities


def _make_camera(
    *, profiles: list[StreamProfile] | None = None, rtsp_url_override: str | None = None
) -> Camera:
    if profiles is None:
        profiles = [
            StreamProfile(
                name="Main",
                resolution=Resolution(width=1920, height=1080),
                codec=Codec.H264,
                bitrate=BitrateKbps(value=4096),
                fps=25,
                onvif_token="Profile_1",
            )
        ]
    return Camera(
        name="cam-1",
        ip_address="10.0.0.5",
        username="admin",
        password="secret",
        stream_profiles=profiles,
        rtsp_url_override=rtsp_url_override,
    )


class FakeCameraRepository(ICameraRepository):
    def __init__(self, cameras: dict[UUID, Camera] | None = None) -> None:
        self.cameras = cameras or {}

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


class FakeCameraGateway(ICameraGateway):
    def __init__(self, *, fail_get_stream_uri: Exception | None = None) -> None:
        self._fail_get_stream_uri = fail_get_stream_uri
        self.connect_calls: list[tuple[str, str, str, int]] = []
        self.disconnected = False

    async def connect(self, ip_address: str, username: str, password: str, port: int = 80) -> None:
        self.connect_calls.append((ip_address, username, password, port))

    async def get_device_info(self) -> Camera:
        raise NotImplementedError

    async def get_profiles(self) -> list[StreamProfile]:
        raise NotImplementedError

    async def get_video_encoder_configuration(self, profile_id: str) -> StreamProfile:
        raise NotImplementedError

    async def set_video_encoder_configuration(
        self, profile_id: str, profile: StreamProfile
    ) -> None:
        raise NotImplementedError

    async def get_video_encoder_configuration_options(
        self, profile_id: str
    ) -> VideoEncoderCapabilities:
        raise NotImplementedError

    async def get_stream_uri(self, profile_id: str) -> str:
        if self._fail_get_stream_uri is not None:
            raise self._fail_get_stream_uri
        return "rtsp://camera.invalid/stream"

    async def disconnect(self) -> None:
        self.disconnected = True


class FakeRecordingRepository(IRecordingRepository):
    def __init__(self) -> None:
        self.recordings: dict[UUID, Recording] = {}

    async def add(self, recording: Recording) -> None:
        self.recordings[recording.id] = recording

    async def get(self, recording_id: UUID) -> Recording | None:
        return self.recordings.get(recording_id)

    async def list(
        self,
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Recording]:
        return list(self.recordings.values())

    async def update(self, recording: Recording) -> None:
        self.recordings[recording.id] = recording

    async def delete(self, recording_id: UUID) -> None:
        self.recordings.pop(recording_id, None)


class FakeRecordingWorker(IRecordingWorker):
    """No real subprocess — records `start`/`stop` calls."""

    def __init__(self, camera_id: UUID, rtsp_url: str) -> None:
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.started = False
        self.stopped = False
        self._recording_id = uuid4()

    async def start(self) -> Recording:
        self.started = True
        return Recording(
            id=self._recording_id,
            camera_id=self.camera_id,
            file_path=f"/storage/recordings/{self.camera_id}/session_000.mp4",
            started_at=datetime.now(UTC),
        )

    async def stop(self) -> list[Recording]:
        self.stopped = True
        return []


def _build_use_case(
    camera_repository: ICameraRepository,
    gateway: ICameraGateway,
    recording_repository: IRecordingRepository,
    registry: RecordingSessionRegistry,
    built_workers: list[FakeRecordingWorker] | None = None,
) -> StartRecordingUseCase:
    built_workers = built_workers if built_workers is not None else []

    def build_recording_worker(camera_id: UUID, rtsp_url: str) -> FakeRecordingWorker:
        worker = FakeRecordingWorker(camera_id, rtsp_url)
        built_workers.append(worker)
        return worker

    return StartRecordingUseCase(
        camera_gateway_factory=lambda: gateway,
        camera_repository=camera_repository,
        recording_repository=recording_repository,
        registry=registry,
        build_recording_worker=build_recording_worker,  # type: ignore[arg-type]
    )


async def test_execute_raises_camera_not_found_for_unknown_camera() -> None:
    use_case = _build_use_case(
        FakeCameraRepository(),
        FakeCameraGateway(),
        FakeRecordingRepository(),
        RecordingSessionRegistry(),
    )
    with pytest.raises(CameraNotFoundError):
        await use_case.execute(UUID(int=1))


async def test_execute_raises_unsupported_configuration_with_no_onvif_token() -> None:
    camera = _make_camera(
        profiles=[
            StreamProfile(
                name="Audio-only",
                resolution=Resolution(width=1920, height=1080),
                codec=Codec.H264,
                bitrate=BitrateKbps(value=4096),
                fps=25,
                onvif_token=None,
            )
        ]
    )
    repository = FakeCameraRepository({camera.id: camera})
    use_case = _build_use_case(
        repository, FakeCameraGateway(), FakeRecordingRepository(), RecordingSessionRegistry()
    )

    with pytest.raises(UnsupportedConfigurationError):
        await use_case.execute(camera.id)


async def test_execute_propagates_reachability_check_failure() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository({camera.id: camera})
    gateway = FakeCameraGateway(fail_get_stream_uri=CameraAuthenticationError("bad credentials"))
    use_case = _build_use_case(
        repository, gateway, FakeRecordingRepository(), RecordingSessionRegistry()
    )

    with pytest.raises(CameraAuthenticationError):
        await use_case.execute(camera.id)

    assert gateway.disconnected is True


async def test_execute_starts_worker_persists_row_and_is_idempotent() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository({camera.id: camera})
    gateway = FakeCameraGateway()
    recording_repository = FakeRecordingRepository()
    built: list[FakeRecordingWorker] = []
    use_case = _build_use_case(
        repository, gateway, recording_repository, RecordingSessionRegistry(), built
    )

    first = await use_case.execute(camera.id)
    second = await use_case.execute(camera.id)

    assert len(built) == 1
    assert built[0].started is True
    assert built[0].rtsp_url == "rtsp://camera.invalid/stream"
    assert first.id == second.id
    assert await recording_repository.get(first.id) == first


async def test_execute_uses_rtsp_url_override_without_calling_the_gateway() -> None:
    camera = _make_camera(rtsp_url_override="rtsp://public.example:8554/stream")
    repository = FakeCameraRepository({camera.id: camera})
    gateway = FakeCameraGateway()
    built: list[FakeRecordingWorker] = []
    use_case = _build_use_case(
        repository, gateway, FakeRecordingRepository(), RecordingSessionRegistry(), built
    )

    await use_case.execute(camera.id)

    assert gateway.connect_calls == []
    assert built[0].rtsp_url == "rtsp://admin:secret@public.example:8554/stream"
