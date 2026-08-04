from app.application.ports.event_publisher import IEventPublisher
from app.application.ports.frame_source import IFrameSource
from app.application.ports.object_detector import IObjectDetector


class RunAnalyticsPipelineUseCase:
    """Run the detector plugin(s) over every frame from a source and publish events.

    Preconditions: `frame_source` is started and producing frames.

    Postconditions: every `DetectionEvent` a detector emits is published via
    `event_publisher`, identically regardless of what kind of `frame_source`
    this was given (ONVIF camera, raw RTSP, or MP4 file) — the architectural
    guarantee this project is built to prove (see docs/AI_PROJECT_CONTEXT.md §2,
    and the permanent regression test at docs/TASK_BACKLOG.md T-086).

    Real logic (the orchestrator, plugin iteration) lands at M8
    (docs/TASK_BACKLOG.md T-081); this milestone only establishes the signature
    and its dependency on the M1 ports.
    """

    def __init__(
        self,
        frame_source: IFrameSource,
        object_detector: IObjectDetector,
        event_publisher: IEventPublisher,
    ) -> None:
        self._frame_source = frame_source
        self._object_detector = object_detector
        self._event_publisher = event_publisher

    async def execute(self) -> None:
        raise NotImplementedError
