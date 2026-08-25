from app.application.ports.rtmp_server_controller import IRtmpServerController
from app.domain.value_objects.rtmp_server_status import RtmpServerStatus


class ManageRtmpServerUseCase:
    """Start/stop/observe the RTMP demo server (MediaMTX) — docs/RTMP_DEMO.md.

    A thin wrapper over `IRtmpServerController`, kept as its own use case
    (rather than folding server control into the publisher/consumer use
    cases) so the three lifecycles the RTMP demo needs — server, publisher,
    consumer — stay independently controllable and independently testable.
    """

    def __init__(self, controller: IRtmpServerController) -> None:
        self._controller = controller

    async def execute(self) -> None:
        await self._controller.start()

    async def stop(self) -> None:
        await self._controller.stop()

    def status(self) -> RtmpServerStatus:
        return self._controller.status()
