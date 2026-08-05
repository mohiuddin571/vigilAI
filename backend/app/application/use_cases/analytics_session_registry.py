import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.application.use_cases.run_analytics_pipeline import RunAnalyticsPipelineUseCase


@dataclass
class _AnalyticsSession:
    use_case: RunAnalyticsPipelineUseCase
    task: "asyncio.Task[None]"


class AnalyticsSessionRegistry:
    """Enable/disable/observe the analytics pipeline, one supervised session per source (T-085).

    Mirrors `StartLiveStreamUseCase`'s internal per-camera registry shape
    (docs/TECHNICAL_DECISIONS.md TD-21) generalized to `source_id` — M8 has
    no ONVIF camera dependency, so a source-agnostic string id is the right
    key (matching `IFrameSource.source_id`), not a persisted `Camera` UUID.

    `enable(source_id)` is idempotent: the first call builds a fresh
    `RunAnalyticsPipelineUseCase` via `build_use_case` and starts its
    `execute()` loop as a background task; a later call while already
    running just re-enables an existing (possibly disabled) session rather
    than starting a second one. `disable(source_id)` never touches the
    session's task or frame source — only `RunAnalyticsPipelineUseCase.disable()`
    — so "toggling off stops new events without restarting the stream"
    (T-085's Definition of Done) holds by construction.

    `build_use_case` is `async` (M9, docs/TECHNICAL_DECISIONS.md TD-25) —
    widened from a plain sync callable because resolving a real onboarded
    camera's `source_id` into a frame source requires an `await`ed
    repository lookup (M8's original "mp4-demo"-only source needed no I/O to
    build). An additive signature change, not a redesign.
    """

    def __init__(
        self, build_use_case: Callable[[str], Awaitable[RunAnalyticsPipelineUseCase]]
    ) -> None:
        self._build_use_case = build_use_case
        self._sessions: dict[str, _AnalyticsSession] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def enable(self, source_id: str) -> None:
        async with self._locks[source_id]:
            session = self._sessions.get(source_id)
            if session is not None:
                session.use_case.enable()
                return
            use_case = await self._build_use_case(source_id)
            task = asyncio.create_task(use_case.execute())
            self._sessions[source_id] = _AnalyticsSession(use_case, task)

    async def disable(self, source_id: str) -> None:
        async with self._locks[source_id]:
            session = self._sessions.get(source_id)
            if session is not None:
                session.use_case.disable()

    def is_enabled(self, source_id: str) -> bool:
        session = self._sessions.get(source_id)
        return session is not None and session.use_case.enabled
