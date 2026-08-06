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

    async def process(
        self, frame: Frame, enabled_plugin_ids: frozenset[str] | None = None
    ) -> list[DetectionEvent]:
        """Run every plugin over `frame`, or only those named in `enabled_plugin_ids`.

        `None` (the default) runs every plugin, unchanged from this method's
        original behavior — the composition root binds a specific camera's
        `enabled_plugin_ids` via `functools.partial` when building that
        camera's analytics session (`Container._build_analytics_use_case`),
        so callers elsewhere (e.g. every existing test) are unaffected.
        Skipping a plugin here also skips whatever it would have written into
        `self._context` for later plugins in the list — e.g. disabling
        `yolo_object_detector` while leaving `color_detector`/
        `loitering_detector`/`missing_object_detector` enabled means those
        three see no bounding boxes and emit nothing, not an error (T-100/
        T-113/T-121's context handoff, docs/TECHNICAL_DECISIONS.md
        TD-27/TD-28/TD-29).
        """
        events: list[DetectionEvent] = []
        for plugin in self._plugins:
            if enabled_plugin_ids is not None and plugin.plugin_id not in enabled_plugin_ids:
                continue
            events.extend(await plugin.process(frame, self._context))
        return events
