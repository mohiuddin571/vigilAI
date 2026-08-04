"""T-064: proves the live-view and recording code paths share no exclusive
resource — the actual argument being made in
docs/TECHNICAL_DECISIONS.md TD-22 for why the two don't interfere.

This is a fakes-based proxy for the real claim, not a live-camera/ffmpeg
proof: `StartLiveStreamUseCase` keeps its own `_streams` registry
(per-camera `asyncio.Lock`s) and `StartRecordingUseCase`/`StopRecordingUseCase`
keep an entirely separate `RecordingSessionRegistry` — nothing here is
shared, so starting/stopping one can never block or cancel the other. The
ffmpeg-and-real-RTSP half of this claim is covered (skip-guarded, since
`ffmpeg` isn't installed in this environment) by
`tests/integration/streaming/test_recordings_api_integration.py`.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import numpy as np

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.application.use_cases.start_recording import StartRecordingUseCase
from app.domain.entities.camera import Camera
from app.domain.entities.frame import Frame
from app.domain.entities.recording import Recording
from app.domain.entities.stream_profile import StreamProfile
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.stream_health import StreamHealth, StreamState

from .test_start_recording import FakeCameraGateway as FakeRecordingCameraGateway
from .test_start_recording import FakeRecordingRepository


def _make_camera() -> Camera:
    return Camera(
        name="cam-1",
        ip_address="10.0.0.5",
        username="admin",
        password="secret",
        stream_profiles=[
            StreamProfile(
                name="Main",
                resolution=Resolution(width=1920, height=1080),
                codec=Codec.H264,
                bitrate=BitrateKbps(value=4096),
                fps=25,
                onvif_token="Profile_1",
            )
        ],
    )


class FakeCameraRepository(ICameraRepository):
    def __init__(self, cameras: dict[UUID, Camera]) -> None:
        self.cameras = cameras

    async def add(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera

    async def get(self, camera_id: UUID) -> Camera | None:
        return self.cameras.get(camera_id)

    async def list(self) -> list[Camera]:
        return list(self.cameras.values())

    async def update(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera


class FakeStreamCameraGateway(ICameraGateway):
    async def connect(self, ip_address: str, username: str, password: str, port: int = 80) -> None:
        pass

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

    async def get_video_encoder_configuration_options(self, profile_id: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def get_stream_uri(self, profile_id: str) -> str:
        return "rtsp://camera.invalid/stream"

    async def disconnect(self) -> None:
        pass


class FakeStreamWorker:
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        self.started = False
        self._release = asyncio.Event()

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self._release.set()

    async def frames(self) -> AsyncIterator[Frame]:
        yield Frame(
            source_id=self.source_id,
            sequence=0,
            timestamp=datetime.now(UTC),
            image=np.zeros((2, 2, 3), dtype=np.uint8),
        )
        await self._release.wait()

    def health(self) -> StreamHealth:
        return StreamHealth(state=StreamState.CONNECTED if self.started else StreamState.STOPPED)


class FakeRecordingWorker:
    def __init__(self, camera_id: UUID, rtsp_url: str) -> None:
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.started = False

    async def start(self) -> Recording:
        self.started = True
        return Recording(
            camera_id=self.camera_id,
            file_path=f"/storage/recordings/{self.camera_id}/session_000.mp4",
            started_at=datetime.now(UTC),
        )

    async def stop(self) -> list[Recording]:
        return []


async def test_live_stream_and_recording_run_concurrently_without_interference() -> None:
    camera = _make_camera()
    cameras = {camera.id: camera}

    live_stream_use_case = StartLiveStreamUseCase(
        camera_gateway_factory=FakeStreamCameraGateway,
        camera_repository=FakeCameraRepository(cameras),
        build_stream_worker=lambda cam, profile: FakeStreamWorker(str(cam.id)),  # type: ignore[arg-type,return-value]
    )
    recording_use_case = StartRecordingUseCase(
        camera_gateway_factory=lambda: FakeRecordingCameraGateway(),
        camera_repository=FakeCameraRepository(cameras),
        recording_repository=FakeRecordingRepository(),
        registry=RecordingSessionRegistry(),
        build_recording_worker=FakeRecordingWorker,  # type: ignore[arg-type]
    )

    await asyncio.gather(
        live_stream_use_case.execute(camera.id), recording_use_case.execute(camera.id)
    )

    assert live_stream_use_case.health(camera.id).state == StreamState.CONNECTED
    recording = await recording_use_case.execute(camera.id)  # idempotent re-check
    assert recording.camera_id == camera.id

    await live_stream_use_case.stop(camera.id)
    assert live_stream_use_case.health(camera.id).state == StreamState.STOPPED
