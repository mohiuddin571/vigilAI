import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.domain.entities.detection_event import DetectionEvent
from app.interfaces.schemas.analytics import DetectionEventResponse

_DEFAULT_QUEUE_MAX_SIZE = 50


def _put_drop_oldest(q: "asyncio.Queue[DetectionEvent]", item: DetectionEvent) -> None:
    try:
        q.put_nowait(item)
    except asyncio.QueueFull:
        with contextlib.suppress(asyncio.QueueEmpty):
            q.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(item)


class AnalyticsEventsHub:
    """In-process fan-out of published `DetectionEvent`s to N connected WebSocket clients (T-084).

    An analogous multi-viewer problem to TD-21's MJPEG fan-out, but a
    different shape: MJPEG viewers only ever want the *latest* frame (an
    `asyncio.Condition` over one shared value, dropping missed frames is
    fine — TD-10's documented tradeoff), while analytics events are
    discrete, individually meaningful occurrences a client shouldn't
    silently skip past under normal load. So each connection gets its own
    bounded, drop-oldest `asyncio.Queue` (the same bounded/drop-oldest
    convention T-023 established for frame queues) rather than sharing one
    "latest value" — a slow viewer only drops the *oldest* backlog, not
    arbitrary events, and never blocks `EventBus.publish()` or other
    viewers.

    `broadcast` matches `IEventPublisher.subscribe`'s handler signature, so
    the composition root wires it in with `event_bus.subscribe(hub.broadcast)`.
    """

    def __init__(self, max_queue_size: int = _DEFAULT_QUEUE_MAX_SIZE) -> None:
        self._queues: set[asyncio.Queue[DetectionEvent]] = set()
        self._max_queue_size = max_queue_size

    async def broadcast(self, event: DetectionEvent) -> None:
        for queue in list(self._queues):
            _put_drop_oldest(queue, event)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator["asyncio.Queue[DetectionEvent]"]:
        queue: asyncio.Queue[DetectionEvent] = asyncio.Queue(maxsize=self._max_queue_size)
        self._queues.add(queue)
        try:
            yield queue
        finally:
            self._queues.discard(queue)


def create_analytics_events_router(hub: AnalyticsEventsHub) -> APIRouter:
    """Build the `/ws/analytics/events` WebSocket channel (T-084).

    One global channel across every analytics-enabled source for M8 — no
    acceptance criterion requires per-source filtering yet, and M8 only ever
    has one enableable source (the MP4 demo). A natural per-source filter
    (`?source_id=`) is a small, additive extension once M9+ wires real
    cameras with multiple concurrently-enabled sources.
    """
    router = APIRouter()

    @router.websocket("/ws/analytics/events")
    async def analytics_events_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            async with hub.subscribe() as queue:
                while True:
                    event = await queue.get()
                    response = DetectionEventResponse.from_domain(event)
                    await websocket.send_json(response.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            with contextlib.suppress(RuntimeError):
                await websocket.close()

    return router
