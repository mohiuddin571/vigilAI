import asyncio
import contextlib
from collections import defaultdict
from collections.abc import AsyncIterator, Callable
from uuid import UUID

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.ports.stream_worker import IStreamWorker
from app.domain.entities.camera import Camera
from app.domain.entities.frame import Frame
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import (
    CameraNotFoundError,
    FrameSourceUnavailableError,
    UnsupportedConfigurationError,
)
from app.domain.value_objects.stream_health import StreamHealth, StreamState


class _StreamHandle:
    """One running camera's Stream Worker plus in-process fan-out to N viewers.

    `IStreamWorker.frames()` drains a single `multiprocessing.Queue` (M2) —
    a second concurrent caller of `worker.frames()` would race the first for
    items rather than each seeing the full stream. So exactly one internal
    task (`_consume`) drains the worker, and every external viewer (e.g. each
    MJPEG HTTP connection) gets its own `frames()` generator fed off a shared
    `asyncio.Condition`, per TD-10's documented multi-viewer tradeoff — a slow
    viewer misses frames rather than blocking the others or the worker.
    """

    def __init__(self, worker: IStreamWorker) -> None:
        self.worker = worker
        self._latest_frame: Frame | None = None
        self._condition = asyncio.Condition()
        self._stopped = False
        self.consume_task: asyncio.Task[None] | None = None

    async def start_consuming(self) -> None:
        self.consume_task = asyncio.create_task(self._consume())

    async def _consume(self) -> None:
        async for frame in self.worker.frames():
            async with self._condition:
                self._latest_frame = frame
                self._condition.notify_all()

    async def frames(self) -> AsyncIterator[Frame]:
        last_sequence: int | None = None
        while True:

            def _has_new_frame(seq: int | None = last_sequence) -> bool:
                return self._stopped or (
                    self._latest_frame is not None and self._latest_frame.sequence != seq
                )

            async with self._condition:
                await self._condition.wait_for(_has_new_frame)
                if self._stopped:
                    return
                frame = self._latest_frame
            assert frame is not None
            last_sequence = frame.sequence
            yield frame

    def health(self) -> StreamHealth:
        return self.worker.health()

    async def stop(self) -> None:
        if self.consume_task is not None:
            self.consume_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.consume_task
            self.consume_task = None
        await self.worker.stop()
        async with self._condition:
            self._stopped = True
            self._condition.notify_all()


def _select_stream_profile(camera: Camera, profile_id: str | None) -> StreamProfile:
    """Pick the `StreamProfile` to resolve a live stream for.

    Raises:
        UnsupportedConfigurationError: `profile_id` was given but doesn't
            match any of the camera's profiles, or no profile (explicit or
            auto-selected) has an `onvif_token` to address on the camera.
    """
    if profile_id is not None:
        for profile in camera.stream_profiles:
            if profile.onvif_token == profile_id:
                return profile
        raise UnsupportedConfigurationError(
            f"Camera {camera.id} has no stream profile {profile_id!r}"
        )

    for profile in camera.stream_profiles:
        if profile.is_primary and profile.onvif_token is not None:
            return profile
    for profile in camera.stream_profiles:
        if profile.onvif_token is not None:
            return profile
    raise UnsupportedConfigurationError(
        f"Camera {camera.id} has no stream profile with an ONVIF token to stream from"
    )


class StartLiveStreamUseCase:
    """Start/stop/observe live streams, one supervised Stream Worker per camera.

    Preconditions: `camera_id` identifies a previously onboarded camera with
    at least one stream profile carrying an ONVIF token.

    Postconditions: a Stream Worker is running for the camera and frames are
    available (via `frames(camera_id)`) for live-view/analytics consumers;
    `health(camera_id)` reflects its supervised connection state.

    Raises:
        CameraNotFoundError: no onboarded camera exists for `camera_id`.
        CameraUnreachableError / CameraAuthenticationError: the upfront
            `get_stream_uri` reachability check (see below) failed.
        UnsupportedConfigurationError: no usable stream profile.

    Shaped like M2's `DebugStreamUseCase` (docs/TASK_BACKLOG.md T-025), a
    stateful non-persisted use case managing running workers rather than
    reading/writing a repository — generalized here to one worker per
    `camera_id` instead of a single global one (docs/TECHNICAL_DECISIONS.md
    TD-21).

    `execute()` also does one upfront `camera_gateway.connect()` ->
    `get_stream_uri()` -> `disconnect()` cycle purely as a fail-fast
    reachability/credential check, so a currently-unreachable camera or bad
    credentials surface as a synchronous typed 4xx from the start endpoint
    instead of only being observable later via `health()`. The actual
    supervised worker (`OnvifRtspFrameSource`, built by `build_stream_worker`)
    re-resolves the stream URI itself on every connect/reconnect attempt
    independently of this check (TD-21) — the URI/credentials resolved here
    are never logged or persisted (TD-15).
    """

    def __init__(
        self,
        camera_gateway_factory: Callable[[], ICameraGateway],
        camera_repository: ICameraRepository,
        build_stream_worker: Callable[[Camera, StreamProfile], IStreamWorker],
    ) -> None:
        self._camera_gateway_factory = camera_gateway_factory
        self._camera_repository = camera_repository
        self._build_stream_worker = build_stream_worker
        self._streams: dict[UUID, _StreamHandle] = {}
        self._locks: dict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def execute(self, camera_id: UUID, profile_id: str | None = None) -> None:
        async with self._locks[camera_id]:
            if camera_id in self._streams:
                return

            camera = await self._camera_repository.get(camera_id)
            if camera is None:
                raise CameraNotFoundError(f"No onboarded camera with id {camera_id}")
            profile = _select_stream_profile(camera, profile_id)
            assert profile.onvif_token is not None

            # A fresh gateway per call (mirroring `interfaces/api/cameras.py`'s
            # per-request use-case factories): `ICameraGateway` implementations
            # hold per-connection mutable state, and this use case is a
            # long-lived singleton (TD-21) — reusing one gateway instance
            # across concurrent `execute()` calls for different cameras would
            # let their ONVIF sessions corrupt each other.
            gateway = self._camera_gateway_factory()
            try:
                await gateway.connect(
                    camera.ip_address, camera.username, camera.password, camera.port
                )
                await gateway.get_stream_uri(profile.onvif_token)
            finally:
                await gateway.disconnect()

            worker = self._build_stream_worker(camera, profile)
            await worker.start()
            handle = _StreamHandle(worker)
            await handle.start_consuming()
            self._streams[camera_id] = handle

    async def stop(self, camera_id: UUID) -> None:
        async with self._locks[camera_id]:
            handle = self._streams.pop(camera_id, None)
            if handle is None:
                return
            await handle.stop()

    def frames(self, camera_id: UUID) -> AsyncIterator[Frame]:
        handle = self._streams.get(camera_id)
        if handle is None:
            raise FrameSourceUnavailableError(f"No live stream is running for camera {camera_id}")
        return handle.frames()

    def health(self, camera_id: UUID) -> StreamHealth:
        handle = self._streams.get(camera_id)
        if handle is None:
            return StreamHealth(state=StreamState.STOPPED)
        return handle.health()
