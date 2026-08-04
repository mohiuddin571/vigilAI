from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from app.application.ports.detector_plugin import IDetectorPlugin
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame


class NoOpDetectorPlugin(IDetectorPlugin):
    """A trivial passthrough plugin proving the orchestrator wiring end-to-end (T-081).

    Not a real detector (M9+ is where real detection lands, see
    docs/IMPLEMENTATION_PLAN.md §M8's Deliverables text) — emits exactly one
    `DetectionEvent` per frame it sees, so "analytics can be toggled on ...
    and events (even from the no-op plugin) appear over WebSocket and in the
    event table" (M8's acceptance criterion) is literally demonstrable.

    `DetectionEvent.camera_id` (M1-fixed, required `UUID`) has no real
    onboarded `Camera` to point at for a bare frame-source id like
    "mp4-demo" — a deterministic `uuid5` derived from `frame.source_id` is
    used instead of a random one, so the same source always maps to the same
    id; the literal `source_id` is also preserved in `metadata` for exact
    traceability (docs/TECHNICAL_DECISIONS.md TD-24).
    """

    @property
    def plugin_id(self) -> str:
        return "noop"

    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        return [
            DetectionEvent(
                camera_id=uuid5(NAMESPACE_DNS, frame.source_id),
                event_type="noop.frame_processed",
                occurred_at=datetime.now(UTC),
                confidence=1.0,
                metadata={"source_id": frame.source_id, "frame_sequence": frame.sequence},
            )
        ]
