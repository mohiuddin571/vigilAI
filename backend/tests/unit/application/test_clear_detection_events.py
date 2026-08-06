from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.ports.event_repository import IEventRepository
from app.application.use_cases.clear_detection_events import ClearDetectionEventsUseCase
from app.domain.entities.detection_event import DetectionEvent


class FakeEventRepository(IEventRepository):
    def __init__(self, events: list[DetectionEvent] | None = None) -> None:
        self.events: list[DetectionEvent] = list(events or [])
        self.delete_calls: list[tuple] = []

    async def add(self, event: DetectionEvent) -> None:
        self.events.append(event)

    async def list(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DetectionEvent]:
        return [
            e
            for e in self.events
            if (camera_id is None or e.camera_id == camera_id)
            and (event_type is None or e.event_type == event_type)
        ]

    async def delete(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        self.delete_calls.append((camera_id, event_type, start, end))
        matching = await self.list(camera_id, event_type, start, end)
        self.events = [e for e in self.events if e not in matching]
        return len(matching)


def _make_event(camera_id: UUID, event_type: str = "object_detection.chair") -> DetectionEvent:
    return DetectionEvent(
        camera_id=camera_id,
        event_type=event_type,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        confidence=0.9,
    )


async def test_clear_all_events_with_no_filters() -> None:
    camera_a, camera_b = uuid4(), uuid4()
    repository = FakeEventRepository([_make_event(camera_a), _make_event(camera_b)])
    use_case = ClearDetectionEventsUseCase(repository)

    deleted_count = await use_case.execute()

    assert deleted_count == 2
    assert repository.events == []


async def test_clear_events_scoped_to_one_camera() -> None:
    camera_a, camera_b = uuid4(), uuid4()
    event_b = _make_event(camera_b)
    repository = FakeEventRepository([_make_event(camera_a), event_b])
    use_case = ClearDetectionEventsUseCase(repository)

    deleted_count = await use_case.execute(camera_id=camera_a)

    assert deleted_count == 1
    assert repository.events == [event_b]


async def test_clear_events_passes_every_filter_through() -> None:
    repository = FakeEventRepository()
    use_case = ClearDetectionEventsUseCase(repository)
    camera_id = uuid4()
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 2)

    await use_case.execute(
        camera_id=camera_id,
        event_type="loitering_detection.dwell_exceeded",
        start=start,
        end=end,
    )

    assert repository.delete_calls == [
        (camera_id, "loitering_detection.dwell_exceeded", start, end)
    ]
