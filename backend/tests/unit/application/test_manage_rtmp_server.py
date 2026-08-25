from app.application.ports.rtmp_server_controller import IRtmpServerController
from app.application.use_cases.manage_rtmp_server import ManageRtmpServerUseCase
from app.domain.value_objects.rtmp_server_status import RtmpServerStatus


class FakeRtmpServerController(IRtmpServerController):
    """A fake `IRtmpServerController` double — no subprocess, no I/O."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True
        self.started = False

    def status(self) -> RtmpServerStatus:
        return RtmpServerStatus(
            running=self.started,
            pid=1234 if self.started else None,
            host="localhost",
            port=1935,
            app_name="live",
            stream_key="demo-camera",
        )


async def test_status_before_start_is_not_running() -> None:
    use_case = ManageRtmpServerUseCase(FakeRtmpServerController())
    status = use_case.status()
    assert status.running is False
    assert status.pid is None


async def test_execute_starts_the_server() -> None:
    controller = FakeRtmpServerController()
    use_case = ManageRtmpServerUseCase(controller)

    await use_case.execute()

    assert controller.started is True
    assert use_case.status().running is True


async def test_stop_stops_the_server() -> None:
    controller = FakeRtmpServerController()
    use_case = ManageRtmpServerUseCase(controller)
    await use_case.execute()

    await use_case.stop()

    assert controller.stopped is True
    assert use_case.status().running is False


async def test_stop_is_a_no_op_when_never_started() -> None:
    use_case = ManageRtmpServerUseCase(FakeRtmpServerController())
    await use_case.stop()  # must not raise
    assert use_case.status().running is False
