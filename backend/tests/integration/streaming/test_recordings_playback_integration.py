"""T-070: `GET /recordings/{id}/media` HTTP range-request playback endpoint.

Verified against the real, already-committed `sample.mp4` fixture (M2, TD-20)
— unlike `test_recordings_api_integration.py`, this doesn't need `ffmpeg`/
`ffprobe` at all, since it only serves an existing file rather than producing
one, so it is not skip-guarded.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.get_recording import GetRecordingUseCase
from app.application.use_cases.list_recordings import ListRecordingsUseCase
from app.core.exception_handlers import register_exception_handlers
from app.domain.entities.recording import Recording
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.recording_repository import SqlRecordingRepository
from app.interfaces.api.recordings import create_recordings_router

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"


def _unexercised() -> NoReturn:
    raise NotImplementedError("start/stop recording are not exercised by this test")


async def _build_app(db_path: Path) -> tuple[FastAPI, SqlRecordingRepository]:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    recording_repository = SqlRecordingRepository(build_session_factory(engine))

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        create_recordings_router(
            build_start_recording_use_case=_unexercised,
            build_stop_recording_use_case=_unexercised,
            build_list_recordings_use_case=lambda: ListRecordingsUseCase(recording_repository),
            build_get_recording_use_case=lambda: GetRecordingUseCase(recording_repository),
        )
    )
    return app, recording_repository


def _make_recording(file_path: str) -> Recording:
    return Recording(
        camera_id=uuid4(), file_path=file_path, started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )


async def test_full_get_returns_200_with_the_whole_file(tmp_path: Path) -> None:
    app, repository = await _build_app(tmp_path / "recordings.db")
    recording = _make_recording(str(_FIXTURE_PATH))
    await repository.add(recording)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/recordings/{recording.id}/media")

    assert response.status_code == 200
    assert response.content == _FIXTURE_PATH.read_bytes()
    assert response.headers["accept-ranges"] == "bytes"


async def test_partial_get_returns_206_with_the_requested_byte_range(tmp_path: Path) -> None:
    app, repository = await _build_app(tmp_path / "recordings.db")
    recording = _make_recording(str(_FIXTURE_PATH))
    await repository.add(recording)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/recordings/{recording.id}/media", headers={"Range": "bytes=0-99"}
        )

    file_size = _FIXTURE_PATH.stat().st_size
    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 0-99/{file_size}"
    assert response.content == _FIXTURE_PATH.read_bytes()[:100]


async def test_get_media_for_unknown_recording_id_returns_404(tmp_path: Path) -> None:
    app, _repository = await _build_app(tmp_path / "recordings.db")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/recordings/{uuid4()}/media")

    assert response.status_code == 404


async def test_get_media_for_a_row_whose_file_is_missing_from_disk_returns_404(
    tmp_path: Path,
) -> None:
    app, repository = await _build_app(tmp_path / "recordings.db")
    recording = _make_recording(str(tmp_path / "does-not-exist.mp4"))
    await repository.add(recording)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/recordings/{recording.id}/media")

    assert response.status_code == 404
