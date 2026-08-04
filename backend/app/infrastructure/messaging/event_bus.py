import asyncio
from collections.abc import Awaitable, Callable

from app.application.ports.event_publisher import IEventPublisher
from app.domain.entities.detection_event import DetectionEvent


class EventBus(IEventPublisher):
    """In-process asyncio pub-sub `IEventPublisher` implementation (T-082, TD-11).

    Reaches persistence and any live WebSocket subscribers without the
    `AnalyticsOrchestrator`/`RunAnalyticsPipelineUseCase` knowing about
    either (docs/ARCHITECTURE.md §6.4) — the composition root subscribes
    both `SqlEventRepository.add` and `AnalyticsEventsHub.broadcast`.
    """

    def __init__(self) -> None:
        self._handlers: list[Callable[[DetectionEvent], Awaitable[None]]] = []

    def subscribe(self, handler: Callable[[DetectionEvent], Awaitable[None]]) -> None:
        self._handlers.append(handler)

    async def publish(self, event: DetectionEvent) -> None:
        if not self._handlers:
            return
        await asyncio.gather(*(handler(event) for handler in self._handlers))
