from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.detection_event import DetectionEvent
from app.infrastructure.messaging.event_bus import EventBus


def _event() -> DetectionEvent:
    return DetectionEvent(
        camera_id=uuid4(), event_type="test.event", occurred_at=datetime.now(UTC), confidence=1.0
    )


async def test_publish_with_no_subscribers_does_not_raise() -> None:
    bus = EventBus()
    await bus.publish(_event())


async def test_multiple_subscribers_all_receive_a_published_event() -> None:
    bus = EventBus()
    received_a: list[DetectionEvent] = []
    received_b: list[DetectionEvent] = []

    async def handler_a(event: DetectionEvent) -> None:
        received_a.append(event)

    async def handler_b(event: DetectionEvent) -> None:
        received_b.append(event)

    bus.subscribe(handler_a)
    bus.subscribe(handler_b)

    event = _event()
    await bus.publish(event)

    assert received_a == [event]
    assert received_b == [event]


async def test_events_published_in_order_are_delivered_in_order_per_subscriber() -> None:
    bus = EventBus()
    received: list[DetectionEvent] = []

    async def handler(event: DetectionEvent) -> None:
        received.append(event)

    bus.subscribe(handler)

    first, second = _event(), _event()
    await bus.publish(first)
    await bus.publish(second)

    assert received == [first, second]
