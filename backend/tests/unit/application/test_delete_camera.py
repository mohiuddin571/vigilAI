from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.application.ports.camera_repository import ICameraRepository
from app.application.ports.event_repository import IEventRepository
from app.application.ports.recording_file_store import IRecordingFileStore
from app.application.ports.recording_repository import IRecordingRepository
from app.application.use_cases.delete_camera import DeleteCameraUseCase
from app.application.use_cases.delete_recording import DeleteRecordingUseCase
from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.entities.camera import Camera
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.recording import Recording
from app.domain.exceptions import (
    CameraNotFoundError,
    FrameSourceUnavailableError,
    RecordingNotInProgressError,
)

_POLYGON = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]


class FakeCameraRepository(ICameraRepository):
    def __init__(self, cameras: list[Camera] | None = None) -> None:
        self.cameras: dict[UUID, Camera] = {c.id: c for c in cameras or []}

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


class FakeZoneRepository(IAnalyticsZoneRepository):
    def __init__(self, zones: list[AnalyticsZone] | None = None) -> None:
        self.zones: dict[UUID, AnalyticsZone] = {z.id: z for z in zones or []}

    async def add(self, zone: AnalyticsZone) -> None:
        self.zones[zone.id] = zone

    async def get(self, zone_id: UUID) -> AnalyticsZone | None:
        return self.zones.get(zone_id)

    async def list_by_camera(self, camera_id: UUID) -> list[AnalyticsZone]:
        return [z for z in self.zones.values() if z.camera_id == camera_id]

    async def update(self, zone: AnalyticsZone) -> None:
        self.zones[zone.id] = zone

    async def delete(self, zone_id: UUID) -> None:
        self.zones.pop(zone_id, None)


class FakeRecordingRepository(IRecordingRepository):
    def __init__(self, recordings: list[Recording] | None = None) -> None:
        self.recordings: dict[UUID, Recording] = {r.id: r for r in recordings or []}

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
        return [
            r for r in self.recordings.values() if camera_id is None or r.camera_id == camera_id
        ]

    async def update(self, recording: Recording) -> None:
        self.recordings[recording.id] = recording

    async def delete(self, recording_id: UUID) -> None:
        self.recordings.pop(recording_id, None)


class FakeRecordingFileStore(IRecordingFileStore):
    def __init__(self) -> None:
        self.deleted_paths: list[str] = []

    async def delete(self, file_path: str) -> None:
        self.deleted_paths.append(file_path)


class FakeEventRepository(IEventRepository):
    def __init__(self, events: list[DetectionEvent] | None = None) -> None:
        self.events: list[DetectionEvent] = list(events or [])
        self.delete_calls: list[UUID | None] = []

    async def add(self, event: DetectionEvent) -> None:
        self.events.append(event)

    async def list(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DetectionEvent]:
        return [e for e in self.events if camera_id is None or e.camera_id == camera_id]

    async def delete(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        self.delete_calls.append(camera_id)
        matching = await self.list(camera_id, event_type, start, end)
        self.events = [e for e in self.events if e not in matching]
        return len(matching)


class StubStreamUseCase:
    """Duck-typed stand-in for `StartLiveStreamUseCase` — only `.stop()` is exercised by
    `DeleteCameraUseCase`; `tests/` is excluded from mypy (pyproject.toml), so this doesn't
    need to satisfy the real class's full interface."""

    def __init__(self) -> None:
        self.stopped_camera_ids: list[UUID] = []

    async def stop(self, camera_id: UUID) -> None:
        self.stopped_camera_ids.append(camera_id)


_DEFAULT_STOP_RECORDING_ERROR = RecordingNotInProgressError("no recording")


class StubStopRecordingUseCase:
    def __init__(self, raise_error: Exception | None = _DEFAULT_STOP_RECORDING_ERROR) -> None:
        self._raise_error = raise_error
        self.called_with: list[UUID] = []

    async def execute(self, camera_id: UUID) -> list[Recording]:
        self.called_with.append(camera_id)
        if self._raise_error is not None:
            raise self._raise_error
        return []


class StubAnalyticsRegistry:
    def __init__(self) -> None:
        self.disabled_source_ids: list[str] = []

    async def disable(self, source_id: str) -> None:
        self.disabled_source_ids.append(source_id)


def _make_camera() -> Camera:
    return Camera(name="Front Door", ip_address="10.0.0.5", username="admin")


def _build_use_case(
    camera_repository: FakeCameraRepository,
    zone_repository: FakeZoneRepository,
    recording_repository: FakeRecordingRepository,
    file_store: FakeRecordingFileStore,
    event_repository: FakeEventRepository,
    stream_use_case: StubStreamUseCase,
    stop_recording_use_case: StubStopRecordingUseCase,
    analytics_registry: StubAnalyticsRegistry,
) -> DeleteCameraUseCase:
    return DeleteCameraUseCase(
        camera_repository=camera_repository,
        zone_repository=zone_repository,
        recording_repository=recording_repository,
        delete_recording_use_case=DeleteRecordingUseCase(recording_repository, file_store),
        event_repository=event_repository,
        stream_use_case=stream_use_case,  # type: ignore[arg-type]
        stop_recording_use_case=stop_recording_use_case,  # type: ignore[arg-type]
        analytics_registry=analytics_registry,  # type: ignore[arg-type]
    )


async def test_delete_camera_raises_not_found_for_unknown_id() -> None:
    use_case = _build_use_case(
        FakeCameraRepository(),
        FakeZoneRepository(),
        FakeRecordingRepository(),
        FakeRecordingFileStore(),
        FakeEventRepository(),
        StubStreamUseCase(),
        StubStopRecordingUseCase(),
        StubAnalyticsRegistry(),
    )

    with pytest.raises(CameraNotFoundError):
        await use_case.execute(uuid4())


async def test_delete_camera_stops_stream_recording_and_analytics() -> None:
    camera = _make_camera()
    stream_use_case = StubStreamUseCase()
    stop_recording_use_case = StubStopRecordingUseCase()
    analytics_registry = StubAnalyticsRegistry()
    use_case = _build_use_case(
        FakeCameraRepository([camera]),
        FakeZoneRepository(),
        FakeRecordingRepository(),
        FakeRecordingFileStore(),
        FakeEventRepository(),
        stream_use_case,
        stop_recording_use_case,
        analytics_registry,
    )

    await use_case.execute(camera.id)

    assert stream_use_case.stopped_camera_ids == [camera.id]
    assert stop_recording_use_case.called_with == [camera.id]
    assert analytics_registry.disabled_source_ids == [str(camera.id)]


async def test_delete_camera_ignores_frame_source_unavailable_from_stop_recording() -> None:
    camera = _make_camera()
    camera_repository = FakeCameraRepository([camera])
    use_case = _build_use_case(
        camera_repository,
        FakeZoneRepository(),
        FakeRecordingRepository(),
        FakeRecordingFileStore(),
        FakeEventRepository(),
        StubStreamUseCase(),
        StubStopRecordingUseCase(raise_error=FrameSourceUnavailableError("no segments")),
        StubAnalyticsRegistry(),
    )

    await use_case.execute(camera.id)  # must not raise

    assert camera.id not in camera_repository.cameras


async def test_delete_camera_cascades_zones_recordings_and_events() -> None:
    camera = _make_camera()
    other_camera = _make_camera()
    zone = AnalyticsZone(
        camera_id=camera.id, name="Entrance", polygon=_POLYGON, dwell_threshold_seconds=5.0
    )
    other_zone = AnalyticsZone(
        camera_id=other_camera.id, name="Elsewhere", polygon=_POLYGON, dwell_threshold_seconds=5.0
    )
    recording = Recording(
        camera_id=camera.id,
        file_path="/storage/recordings/cam/seg_000.mp4",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
    )
    other_recording = Recording(
        camera_id=other_camera.id,
        file_path="/storage/recordings/other/seg_000.mp4",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
    )
    event = DetectionEvent(
        camera_id=camera.id,
        event_type="object_detection.chair",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        confidence=0.9,
    )
    other_event = DetectionEvent(
        camera_id=other_camera.id,
        event_type="object_detection.chair",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        confidence=0.9,
    )

    camera_repository = FakeCameraRepository([camera, other_camera])
    zone_repository = FakeZoneRepository([zone, other_zone])
    recording_repository = FakeRecordingRepository([recording, other_recording])
    file_store = FakeRecordingFileStore()
    event_repository = FakeEventRepository([event, other_event])
    use_case = _build_use_case(
        camera_repository,
        zone_repository,
        recording_repository,
        file_store,
        event_repository,
        StubStreamUseCase(),
        StubStopRecordingUseCase(),
        StubAnalyticsRegistry(),
    )

    await use_case.execute(camera.id)

    # This camera's data is gone...
    assert zone.id not in zone_repository.zones
    assert recording.id not in recording_repository.recordings
    assert file_store.deleted_paths == [recording.file_path]
    assert event not in event_repository.events
    assert camera.id not in camera_repository.cameras
    # ...the other camera's data is untouched.
    assert other_zone.id in zone_repository.zones
    assert other_recording.id in recording_repository.recordings
    assert other_event in event_repository.events
    assert other_camera.id in camera_repository.cameras
