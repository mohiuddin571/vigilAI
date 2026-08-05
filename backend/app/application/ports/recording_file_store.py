from abc import ABC, abstractmethod


class IRecordingFileStore(ABC):
    """Deletes a recording segment's file from wherever it's actually stored.

    Kept separate from `IRecordingRepository` (which only persists/retrieves
    `Recording` *metadata*) so `DeleteRecordingUseCase`/`DeleteCameraUseCase` can
    depend on file deletion through a port rather than importing `pathlib`
    directly — application-layer code stays I/O-free per `AGENTS.md`'s
    Engineering Principles ("everything swappable sits behind an interface"),
    matching every other filesystem/network/SOAP concern in this project.
    """

    @abstractmethod
    async def delete(self, file_path: str) -> None:
        """Delete the file at `file_path` if it exists. Never raises for a
        missing file — by the time this runs the row is already gone from
        `IRecordingRepository`, so there's no persisted state left to roll
        back to, and a recording whose file was already missing from disk
        (`RecordingNotFoundError`'s own documented case) must still be
        deletable."""
