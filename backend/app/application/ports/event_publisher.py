from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from app.domain.entities.detection_event import DetectionEvent


class IEventPublisher(ABC):
    """Publishes analytics events to whatever subscribers exist (persistence, WebSocket)."""

    @abstractmethod
    async def publish(self, event: DetectionEvent) -> None: ...

    @abstractmethod
    def subscribe(self, handler: Callable[[DetectionEvent], Awaitable[None]]) -> None: ...
