import contextlib
from uuid import UUID

import structlog

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.application.ports.camera_repository import ICameraRepository
from app.application.ports.event_repository import IEventRepository
from app.application.ports.recording_repository import IRecordingRepository
from app.application.use_cases.analytics_session_registry import AnalyticsSessionRegistry
from app.application.use_cases.delete_recording import DeleteRecordingUseCase
from app.application.use_cases.start_live_stream import StartLiveStreamUseCase
from app.application.use_cases.stop_recording import StopRecordingUseCase
from app.domain.exceptions import (
    CameraNotFoundError,
    FrameSourceUnavailableError,
    RecordingInProgressError,
    RecordingNotInProgressError,
)

logger = structlog.get_logger(__name__)


class DeleteCameraUseCase:
    """Delete an onboarded camera and cascade the deletion to everything scoped to it —
    its zones, recordings (rows + files), and analytics events — after stopping any
    live stream/recording/analytics session currently running for it.

    Cascade order (TECHNICAL_DECISIONS.md TD-32 records why this order, not just what):
    1. Stop the live stream (`StartLiveStreamUseCase.stop`, always a safe no-op if none
       is running) so nothing is still reading frames from this camera once deletion starts.
    2. Stop any in-progress recording (`StopRecordingUseCase`) so its segment file is
       finalized rather than deleted mid-write; a `RecordingNotInProgressError`/
       `FrameSourceUnavailableError` here just means there was nothing to stop or the
       worker produced no segments — either way, cascade continues.
    3. Disable analytics (`AnalyticsSessionRegistry.disable`, also a safe no-op if not
       enabled) so no new events get published for a camera that's about to disappear.
    4. Delete zones, then recordings (file + row, via `DeleteRecordingUseCase`), then
       events — order among these three doesn't matter functionally (none reference each
       other), listed in the same order as `docs/UI_UX_DESIGN.md`'s screen inventory
       (Zones tab, Recordings, Event Center) for readability.
    5. Delete the camera row itself, last — if any step above fails, the camera (and
       therefore the ability to re-run this cascade) is still there to retry against,
       rather than being an orphaned reference to already-partially-deleted data.

    Raises:
        CameraNotFoundError: no camera exists for `camera_id`.
    """

    def __init__(
        self,
        camera_repository: ICameraRepository,
        zone_repository: IAnalyticsZoneRepository,
        recording_repository: IRecordingRepository,
        delete_recording_use_case: DeleteRecordingUseCase,
        event_repository: IEventRepository,
        stream_use_case: StartLiveStreamUseCase,
        stop_recording_use_case: StopRecordingUseCase,
        analytics_registry: AnalyticsSessionRegistry,
    ) -> None:
        self._camera_repository = camera_repository
        self._zone_repository = zone_repository
        self._recording_repository = recording_repository
        self._delete_recording_use_case = delete_recording_use_case
        self._event_repository = event_repository
        self._stream_use_case = stream_use_case
        self._stop_recording_use_case = stop_recording_use_case
        self._analytics_registry = analytics_registry

    async def execute(self, camera_id: UUID) -> None:
        camera = await self._camera_repository.get(camera_id)
        if camera is None:
            raise CameraNotFoundError(f"No camera with id {camera_id}")

        await self._stream_use_case.stop(camera_id)

        with contextlib.suppress(RecordingNotInProgressError, FrameSourceUnavailableError):
            await self._stop_recording_use_case.execute(camera_id)

        await self._analytics_registry.disable(str(camera_id))

        for zone in await self._zone_repository.list_by_camera(camera_id):
            await self._zone_repository.delete(zone.id)

        for recording in await self._recording_repository.list(camera_id=camera_id):
            try:
                await self._delete_recording_use_case.execute(recording.id)
            except RecordingInProgressError:
                # Race with a recording that started after step 2's stop
                # attempt above — logged rather than failing the whole
                # cascade; its row/file are simply left behind this pass.
                logger.warning(
                    "delete_camera.recording_still_in_progress",
                    camera_id=str(camera_id),
                    recording_id=str(recording.id),
                )

        await self._event_repository.delete(camera_id=camera_id)

        await self._camera_repository.delete(camera_id)
