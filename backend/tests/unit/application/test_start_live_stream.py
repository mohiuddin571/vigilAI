import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import numpy as np
import pytest

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.domain.entities.camera import Camera
from app.domain.entities.frame import Frame
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import (
    CameraAuthenticationError,
    CameraNotFoundError,
    FrameSourceUnavailableError,
    UnsupportedConfigurationError,
)
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.stream_health import StreamHealth, StreamState
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities


def _make_camera(*, profiles: list[StreamProfile] | None = None) -> Camera:
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


class FakeCameraGateway(ICameraGateway):
    """No real I/O. Records `connect`/`disconnect` calls; `get_stream_uri`
    optionally fails, to prove `execute()`'s fail-fast reachability check."""

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


class FakeStreamWorker:
    """A fake `IStreamWorker` double — no process, no I/O."""

    def __init__(self, source_id: str, frame_count: int = 3) -> None:
        self.source_id = source_id
        self.started = False
        self.stopped = False
        self._frame_count = frame_count
        self._release = asyncio.Event()

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True
        self._release.set()

    async def frames(self) -> AsyncIterator[Frame]:
        for sequence in range(self._frame_count):
            yield Frame(
                source_id=self.source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.zeros((2, 2, 3), dtype=np.uint8),
            )
            await asyncio.sleep(0)
        await self._release.wait()

    def health(self) -> StreamHealth:
        return StreamHealth(state=StreamState.CONNECTED if self.started else StreamState.STOPPED)


def _build_use_case(
    repository: ICameraRepository,
    gateway: ICameraGateway,
    built_workers: list[FakeStreamWorker] | None = None,
) -> StartLiveStreamUseCase:
    built_workers = built_workers if built_workers is not None else []

    def build_stream_worker(camera: Camera, profile: StreamProfile) -> FakeStreamWorker:
        worker = FakeStreamWorker(source_id=str(camera.id))
        built_workers.append(worker)
        return worker

    return StartLiveStreamUseCase(
        camera_gateway_factory=lambda: gateway,
        camera_repository=repository,
        build_stream_worker=build_stream_worker,  # type: ignore[arg-type]
    )


async def test_execute_raises_camera_not_found_for_unknown_camera() -> None:
    use_case = _build_use_case(FakeCameraRepository(), FakeCameraGateway())
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
    use_case = _build_use_case(repository, FakeCameraGateway())

    with pytest.raises(UnsupportedConfigurationError):
        await use_case.execute(camera.id)


async def test_execute_propagates_reachability_check_failure() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository({camera.id: camera})
    gateway = FakeCameraGateway(fail_get_stream_uri=CameraAuthenticationError("bad credentials"))
    use_case = _build_use_case(repository, gateway)

    with pytest.raises(CameraAuthenticationError):
        await use_case.execute(camera.id)

    assert gateway.disconnected is True
    assert use_case.health(camera.id).state == StreamState.STOPPED


async def test_execute_starts_worker_and_is_idempotent() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository({camera.id: camera})
    gateway = FakeCameraGateway()
    built: list[FakeStreamWorker] = []
    use_case = _build_use_case(repository, gateway, built)

    await use_case.execute(camera.id)
    await use_case.execute(camera.id)

    assert len(built) == 1
    assert built[0].started is True
    assert gateway.connect_calls == [("10.0.0.5", "admin", "secret", 80)]
    assert use_case.health(camera.id).state == StreamState.CONNECTED


async def test_frames_fan_out_to_multiple_viewers() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository({camera.id: camera})
    use_case = _build_use_case(repository, FakeCameraGateway())

    await use_case.execute(camera.id)

    viewer_a = use_case.frames(camera.id)
    viewer_b = use_case.frames(camera.id)

    first_a = await anext(viewer_a)
    first_b = await anext(viewer_b)

    assert first_a.sequence == first_b.sequence == 0
    assert first_a.source_id == str(camera.id)

    await use_case.stop(camera.id)
    assert use_case.health(camera.id).state == StreamState.STOPPED


async def test_frames_raises_when_no_stream_is_running() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository({camera.id: camera})
    use_case = _build_use_case(repository, FakeCameraGateway())

    with pytest.raises(FrameSourceUnavailableError):
        use_case.frames(camera.id)


async def test_stop_is_a_no_op_for_a_stream_that_was_never_started() -> None:
    use_case = _build_use_case(FakeCameraRepository(), FakeCameraGateway())
    await use_case.stop(UUID(int=1))  # must not raise
