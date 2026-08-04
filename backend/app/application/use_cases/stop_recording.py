from uuid import UUID

from app.application.ports.recording_repository import IRecordingRepository
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.domain.entities.recording import Recording
from app.domain.exceptions import FrameSourceUnavailableError, RecordingNotInProgressError


class StopRecordingUseCase:
    """Stop an in-progress recording, finalizing and persisting its segment metadata.

    Preconditions: a recording is currently in progress for `camera_id`
    (started via `StartRecordingUseCase`).

    Postconditions: the Recording Worker's ffmpeg subprocess has exited and
    every segment file it produced has exactly one corresponding, finalized
    `Recording` row in `recording_repository` (the first row, already added
    by `StartRecordingUseCase`, is updated in place; any additional rollover
    segments are added fresh).

    Raises:
        RecordingNotInProgressError: no recording is currently running for
            `camera_id`.
        FrameSourceUnavailableError: the ffmpeg subprocess exited without
            ever finalizing a single segment file — e.g. the RTSP media
            connection itself never became readable despite the earlier
            ONVIF reachability check in `StartRecordingUseCase` succeeding.
            The orphaned in-progress row from `start()` is left as-is
            (`IRecordingRepository` has no delete operation); it stays
            queryable with `ended_at=None` as a record of the failed attempt.
    """

    def __init__(
        self, recording_repository: IRecordingRepository, registry: RecordingSessionRegistry
    ) -> None:
        self._recording_repository = recording_repository
        self._registry = registry

    async def execute(self, camera_id: UUID) -> list[Recording]:
        async with self._registry.lock(camera_id):
            session = self._registry.pop(camera_id)
            if session is None:
                raise RecordingNotInProgressError(
                    f"No recording is currently in progress for camera {camera_id}"
                )

            segments = await session.worker.stop()
            if not segments:
                raise FrameSourceUnavailableError(
                    f"Recording for camera {camera_id} produced no finalized segments"
                )
            for index, segment in enumerate(segments):
                if index == 0:
                    await self._recording_repository.update(segment)
                else:
                    await self._recording_repository.add(segment)
            return segments
