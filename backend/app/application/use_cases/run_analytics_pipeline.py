from collections.abc import Awaitable, Callable

from app.application.ports.event_publisher import IEventPublisher
from app.application.ports.frame_source import IFrameSource
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame


class RunAnalyticsPipelineUseCase:
    """Run the detector plugin(s) over every frame from one source and publish events.

    Preconditions: none beyond a valid `frame_source` — `execute()` owns the
    source's `start()`/`stop()` lifecycle itself (unlike the M1 stub this
    replaces, which assumed an already-started source; that assumption
    didn't survive real implementation, see docs/TECHNICAL_DECISIONS.md
    TD-24).

    Postconditions: every `DetectionEvent` the orchestrator's plugins emit is
    published via `event_publisher`, identically regardless of what kind of
    `frame_source` this was given (ONVIF camera, raw RTSP, or MP4 file) —
    the architectural guarantee this project is built to prove (see
    docs/AI_PROJECT_CONTEXT.md §2, and the permanent regression test at
    docs/TASK_BACKLOG.md T-086).

    `process_frame` is injected as a plain callable (the composition root
    passes `AnalyticsOrchestrator.process`, a bound method) rather than this
    use case depending on `AnalyticsOrchestrator`'s concrete class directly —
    that class lives under `infrastructure/analytics/` per
    docs/FOLDER_STRUCTURE.md, and `application/` may only import `domain/`
    (the Dependency Direction Rule, enforced by the import-linter contract,
    TD-17). Mirrors the existing `build_stream_worker`/`build_recording_worker`
    callable-injection precedent (TD-21/TD-22).

    `enable()`/`disable()` toggle whether frames reaching this pipeline are
    actually processed/published — frames are still drained from
    `frame_source.frames()` either way, so disabling never stops or restarts
    the underlying source (docs/TASK_BACKLOG.md T-085). `execute()` itself
    runs until the source's `frames()` ends or `request_stop()` is called;
    driving multiple sources concurrently and exposing enable/disable per
    source over an API is `AnalyticsSessionRegistry`'s job, not this class's.
    """

    def __init__(
        self,
        frame_source: IFrameSource,
        process_frame: Callable[[Frame], Awaitable[list[DetectionEvent]]],
        event_publisher: IEventPublisher,
    ) -> None:
        self._frame_source = frame_source
        self._process_frame = process_frame
        self._event_publisher = event_publisher
        self._enabled = True
        self._stop_requested = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def request_stop(self) -> None:
        """Ask `execute()`'s loop to end at its next opportunity."""
        self._stop_requested = True

    async def execute(self) -> None:
        await self._frame_source.start()
        try:
            async for frame in self._frame_source.frames():
                if self._stop_requested:
                    break
                if not self._enabled:
                    continue
                for event in await self._process_frame(frame):
                    await self._event_publisher.publish(event)
        finally:
            await self._frame_source.stop()
