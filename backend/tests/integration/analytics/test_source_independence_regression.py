"""T-086: PERMANENT regression test for the assignment's core architectural claim.

Runs the same `AnalyticsOrchestrator` + the same no-op plugin, driven by the
same `RunAnalyticsPipelineUseCase`, once against a real `Mp4FileFrameSource`
(the committed fixture) and once against a fake `IFrameSource` double,
asserting identical plugin-invocation behavior. This is what makes the
"analytics is not coupled to ONVIF/any specific source" claim verifiable
rather than aspirational (docs/AI_PROJECT_CONTEXT.md §2).

Per AGENTS.md § Testing Expectations and § Things AI Must Never Do: this
test must never be deleted or weakened to make an unrelated change pass.
"""

from pathlib import Path
from typing import Any

from app.application.ports.detector_plugin import IDetectorPlugin
from app.application.ports.frame_source import IFrameSource
from app.application.use_cases.run_analytics_pipeline import RunAnalyticsPipelineUseCase
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.infrastructure.analytics.orchestrator import AnalyticsOrchestrator
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource
from tests.fixtures.streaming.bounded_frame_source import BoundedFrameSource

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"


class _InvocationRecordingPlugin(IDetectorPlugin):
    """A no-op plugin that records every `(source_id, sequence)` it was invoked
    with, so invocation behavior can be compared across source types."""

    def __init__(self) -> None:
        self.invocations: list[tuple[str, int]] = []

    @property
    def plugin_id(self) -> str:
        return "recording-noop"

    async def process(self, frame: Frame, context: dict[str, Any]) -> list[DetectionEvent]:
        self.invocations.append((frame.source_id, frame.sequence))
        return []


class _FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[DetectionEvent] = []

    async def publish(self, event: DetectionEvent) -> None:
        self.published.append(event)

    def subscribe(self, handler: object) -> None:  # pragma: no cover - unused by this test
        raise NotImplementedError


async def _run_pipeline(frame_source: IFrameSource) -> _InvocationRecordingPlugin:
    plugin = _InvocationRecordingPlugin()
    orchestrator = AnalyticsOrchestrator([plugin])
    use_case = RunAnalyticsPipelineUseCase(
        frame_source, orchestrator.process, _FakeEventPublisher()  # type: ignore[arg-type]
    )
    await use_case.execute()
    return plugin


async def test_orchestrator_and_plugin_invoked_identically_over_mp4_source() -> None:
    """Real `Mp4FileFrameSource` against the committed fixture, non-looping so
    `execute()` terminates naturally once the file is exhausted."""
    source = Mp4FileFrameSource(file_path=str(_FIXTURE_PATH), source_id="mp4-fixture", loop=False)

    plugin = await _run_pipeline(source)

    assert len(plugin.invocations) > 0
    assert all(source_id == "mp4-fixture" for source_id, _ in plugin.invocations)
    # Invoked exactly once per frame produced, in frame order, no gaps/dupes.
    assert [sequence for _, sequence in plugin.invocations] == list(range(len(plugin.invocations)))


async def test_orchestrator_and_plugin_invoked_identically_over_fake_source() -> None:
    source = BoundedFrameSource("fake-source", frame_count=7)

    plugin = await _run_pipeline(source)

    assert len(plugin.invocations) == 7
    assert all(source_id == "fake-source" for source_id, _ in plugin.invocations)
    assert [sequence for _, sequence in plugin.invocations] == list(range(7))


async def test_invocation_shape_is_identical_across_source_types() -> None:
    """The architectural claim itself: regardless of which `IFrameSource`
    drives it, the same orchestrator+plugin is invoked exactly once per frame
    the source produced, in order, starting at sequence 0 — with no source-
    specific branching anywhere in the orchestrator/use case/plugin code."""
    mp4_source = Mp4FileFrameSource(
        file_path=str(_FIXTURE_PATH), source_id="mp4-fixture", loop=False
    )
    fake_source = BoundedFrameSource("fake-source", frame_count=7)

    mp4_plugin = await _run_pipeline(mp4_source)
    fake_plugin = await _run_pipeline(fake_source)

    def invocation_count(plugin: _InvocationRecordingPlugin) -> int:
        return len(plugin.invocations)

    def is_sequential_from_zero(plugin: _InvocationRecordingPlugin) -> bool:
        return [seq for _, seq in plugin.invocations] == list(range(invocation_count(plugin)))

    assert invocation_count(mp4_plugin) > 0
    assert invocation_count(fake_plugin) > 0
    assert is_sequential_from_zero(mp4_plugin)
    assert is_sequential_from_zero(fake_plugin)
