from pathlib import Path

import structlog

from app.application.ports.recording_file_store import IRecordingFileStore

logger = structlog.get_logger(__name__)


class LocalRecordingFileStore(IRecordingFileStore):
    """`IRecordingFileStore` for the local filesystem — `FfmpegRecordingWorker` (the only writer
    of recording segments, `recording_worker.py`) writes under `Settings.recording_output_dir`,
    so this is this project's only recording-file storage backend for now (TD-01's
    filesystem-for-recordings choice; object storage is a documented future enhancement, not
    implemented here)."""

    async def delete(self, file_path: str) -> None:
        path = Path(file_path)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            # Best-effort (per the port's docstring): a permissions error or a
            # concurrent delete shouldn't block the DB-row deletion this
            # always runs alongside — logged so it isn't silently lost.
            logger.warning(
                "recording_file_store.delete_failed", file_path=file_path, error=str(exc)
            )
