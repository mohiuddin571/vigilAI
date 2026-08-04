from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import FileResponse

from app.application.use_cases.get_recording import GetRecordingUseCase
from app.application.use_cases.list_recordings import ListRecordingsUseCase
from app.application.use_cases.start_recording import StartRecordingUseCase
from app.application.use_cases.stop_recording import StopRecordingUseCase
from app.domain.exceptions import RecordingNotFoundError
from app.interfaces.schemas.recording import RecordingResponse


def create_recordings_router(
    build_start_recording_use_case: Callable[[], StartRecordingUseCase],
    build_stop_recording_use_case: Callable[[], StopRecordingUseCase],
    build_list_recordings_use_case: Callable[[], ListRecordingsUseCase],
    build_get_recording_use_case: Callable[[], GetRecordingUseCase],
) -> APIRouter:
    """Build the recording router (T-063/T-070): `/cameras/{id}/recording/*` + `/recordings`.

    `build_start_recording_use_case`/`build_stop_recording_use_case` return
    the same shared singletons on every call (see
    `container.build_start_recording_use_case`'s docstring) — they hold the
    `RecordingSessionRegistry` state across requests, mirroring
    `streams.py`'s `StartLiveStreamUseCase` factory. `build_list_recordings_use_case`/
    `build_get_recording_use_case` are per-request factories: both use cases
    are stateless.
    """
    router = APIRouter(tags=["recordings"])

    @router.post(
        "/cameras/{camera_id}/recording/start",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=RecordingResponse,
    )
    async def start_recording(camera_id: UUID) -> RecordingResponse:
        recording = await build_start_recording_use_case().execute(camera_id)
        return RecordingResponse.from_domain(recording)

    @router.post(
        "/cameras/{camera_id}/recording/stop",
        status_code=status.HTTP_200_OK,
        response_model=list[RecordingResponse],
    )
    async def stop_recording(camera_id: UUID) -> list[RecordingResponse]:
        segments = await build_stop_recording_use_case().execute(camera_id)
        return [RecordingResponse.from_domain(segment) for segment in segments]

    @router.get("/recordings", response_model=list[RecordingResponse])
    async def list_recordings(
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[RecordingResponse]:
        recordings = await build_list_recordings_use_case().execute(camera_id, start, end)
        return [RecordingResponse.from_domain(recording) for recording in recordings]

    @router.get("/recordings/{recording_id}/media")
    async def get_recording_media(recording_id: UUID) -> FileResponse:
        """Serve a recording's MP4 file via HTTP range requests (T-070).

        `FileResponse` (Starlette) handles `Range`/`Content-Range`/`206`
        natively — no hand-rolled byte-range parsing needed
        (docs/TECHNICAL_DECISIONS.md TD-23). The file path is resolved
        exclusively via `GetRecordingUseCase` → `IRecordingRepository`,
        keyed by `recording_id`; it is never constructed from client input.
        """
        recording = await build_get_recording_use_case().execute(recording_id)
        file_path = Path(recording.file_path)
        if not file_path.is_file():
            raise RecordingNotFoundError(
                f"Recording {recording_id}'s file is missing from disk: {file_path}"
            )
        return FileResponse(path=file_path, media_type="video/mp4")

    return router
