from abc import ABC, abstractmethod
from typing import Any

from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame


class IDetectorPlugin(ABC):
    """A single analytics capability the `AnalyticsOrchestrator` iterates per frame.

    Supersedes the M1 `IObjectDetector` port as the orchestrator-facing
    contract every plugin implements (docs/ARCHITECTURE.md §6.4,
    docs/TECHNICAL_DECISIONS.md TD-24) — `IObjectDetector` is retired rather
    than kept alongside this with overlapping responsibility.

    `context` carries cross-frame state a plugin needs (e.g. track history
    for loitering, a baseline reference for missing-object detection) so
    plugins stay stateless with respect to *each other* while individually
    being allowed internal state via `context`. Owned and shared by the
    `AnalyticsOrchestrator` across the frames of one pipeline run — plugins
    must never read another plugin's private key out of it.

    One narrow, documented exception (T-100, docs/TECHNICAL_DECISIONS.md
    TD-27): `YoloObjectDetector` publishes the current frame's own
    `DetectionEvent`s into `context` under a reserved, exported key
    (`yolo_object_detector.EVENTS_BY_SOURCE_CONTEXT_KEY`, keyed by
    `frame.source_id`) specifically so `ColorDetector` can read the same
    frame's bounding boxes without re-running detection. This is a same-frame
    producer/consumer handoff between two specific, named plugins via one
    specific, named key — not a general license for a plugin to read
    another's private state.
    """

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """A stable identifier for this plugin, used to correlate events/logs."""

    @abstractmethod
    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        """Run this plugin's detection logic over a single frame.

        Must depend on `Frame` only — never on ONVIF/RTSP specifics (see
        AGENTS.md § Things AI Must Never Do).
        """
