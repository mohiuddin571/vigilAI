from collections.abc import Sequence
from typing import Any

from app.application.ports.detector_plugin import IDetectorPlugin
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame


class AnalyticsOrchestrator:
    """Iterates enabled plugins per frame — no plugin-to-plugin coupling.

    See docs/ARCHITECTURE.md §6.4.

    Depends only on `IDetectorPlugin` (a port) and domain types, despite
    living under `infrastructure/analytics/` per docs/FOLDER_STRUCTURE.md's
    folder convention — `RunAnalyticsPipelineUseCase` (application layer)
    never imports this class directly (the import-linter layers contract,
    TD-17, forbids `application` importing `infrastructure`); it receives
    `process` as an injected callable from the composition root instead. See
    docs/TECHNICAL_DECISIONS.md TD-24.

    `context` is one shared, mutable dict for the lifetime of this
    orchestrator instance (i.e. for one pipeline run) — plugins may store
    their own cross-frame state in it (namespaced by `plugin_id` if needed)
    but must never invoke or depend on another plugin's output.
    """

    def __init__(self, plugins: Sequence[IDetectorPlugin]) -> None:
        self._plugins = list(plugins)
        self._context: dict[str, Any] = {}

    async def process(self, frame: Frame) -> list[DetectionEvent]:
        events: list[DetectionEvent] = []
        for plugin in self._plugins:
            events.extend(await plugin.process(frame, self._context))
        return events
