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
