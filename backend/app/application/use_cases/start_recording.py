from collections.abc import Callable
from urllib.parse import quote, urlparse, urlunparse
from uuid import UUID

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.application.ports.recording_repository import IRecordingRepository
from app.application.ports.recording_worker import IRecordingWorker
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.domain.entities.camera import Camera
from app.domain.entities.recording import Recording
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraNotFoundError, UnsupportedConfigurationError


def _select_recording_profile(camera: Camera) -> StreamProfile:
    """Pick the `StreamProfile` to resolve a recording's RTSP source from.

    Same primary-profile-with-onvif-token selection `StartLiveStreamUseCase`
    uses, duplicated here rather than shared (docs/TECHNICAL_DECISIONS.md
    TD-22) to avoid modifying M5's tested code in this milestone's PR.

    Raises:
        UnsupportedConfigurationError: no profile (primary or otherwise) has
            an `onvif_token` to address on the camera.
    """
    for profile in camera.stream_profiles:
        if profile.is_primary and profile.onvif_token is not None:
            return profile
    for profile in camera.stream_profiles:
        if profile.onvif_token is not None:
            return profile
    raise UnsupportedConfigurationError(
        f"Camera {camera.id} has no stream profile with an ONVIF token to record from"
    )


def _add_rtsp_credentials(url: str, username: str, password: str) -> str:
    """Add stored camera credentials to an override URL that has none.

    Duplicated from `infrastructure/streaming/rtsp_frame_source.py`'s helper
    of the same name (docs/TECHNICAL_DECISIONS.md TD-22) — application layer
    cannot import from infrastructure, and this use case needs the identical
    override-handling behavior `OnvifRtspFrameSource` uses so recording and
    live view treat `camera.rtsp_url_override` consistently.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"rtsp", "rtsps"} or parsed.hostname is None or parsed.username:
        return url
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    credentials = f"{quote(username, safe='')}:{quote(password, safe='')}"
    return urlunparse(parsed._replace(netloc=f"{credentials}@{host}{port}"))


class StartRecordingUseCase:
    """Start recording a camera's stream to disk as MP4 segments.

    Preconditions: `camera_id` identifies a previously onboarded camera with
    at least one stream profile carrying an ONVIF token.

    Postconditions: a Recording Worker is running and a `Recording` row exists
    via `recording_repository` for the in-progress segment.

    Raises:
        CameraNotFoundError: no onboarded camera exists for `camera_id`.
        CameraUnreachableError / CameraAuthenticationError: the upfront
            `get_stream_uri` reachability check failed.
        UnsupportedConfigurationError: no usable stream profile.

    Idempotent like `StartLiveStreamUseCase.execute()`: calling this again
    while a recording is already in progress for `camera_id` returns the
    existing in-progress row rather than starting a second ffmpeg process.

    A stateful singleton (docs/TECHNICAL_DECISIONS.md TD-22, mirroring
    TD-21's `StartLiveStreamUseCase` precedent): `StopRecordingUseCase` needs
    to observe the same running worker across separate HTTP requests, via the
    shared `RecordingSessionRegistry`.
    """

    def __init__(
        self,
        camera_gateway_factory: Callable[[], ICameraGateway],
        camera_repository: ICameraRepository,
        recording_repository: IRecordingRepository,
        registry: RecordingSessionRegistry,
        build_recording_worker: Callable[[UUID, str], IRecordingWorker],
    ) -> None:
        self._camera_gateway_factory = camera_gateway_factory
        self._camera_repository = camera_repository
        self._recording_repository = recording_repository
        self._registry = registry
        self._build_recording_worker = build_recording_worker

    async def execute(self, camera_id: UUID) -> Recording:
        async with self._registry.lock(camera_id):
            existing = self._registry.get(camera_id)
            if existing is not None:
                recording = await self._recording_repository.get(existing.first_recording_id)
                assert recording is not None
                return recording

            camera = await self._camera_repository.get(camera_id)
            if camera is None:
                raise CameraNotFoundError(f"No onboarded camera with id {camera_id}")

            if camera.rtsp_url_override is not None:
                rtsp_url = _add_rtsp_credentials(
                    camera.rtsp_url_override, camera.username, camera.password
                )
            else:
                profile = _select_recording_profile(camera)
                assert profile.onvif_token is not None
                gateway = self._camera_gateway_factory()
                try:
                    await gateway.connect(
                        camera.ip_address, camera.username, camera.password, camera.port
                    )
                    rtsp_url = await gateway.get_stream_uri(profile.onvif_token)
                finally:
                    await gateway.disconnect()

            worker = self._build_recording_worker(camera_id, rtsp_url)
            recording = await worker.start()
            await self._recording_repository.add(recording)
            self._registry.start(camera_id, worker, recording.id)
            return recording
