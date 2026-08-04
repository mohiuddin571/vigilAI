from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.recording import Recording
from app.domain.exceptions import InvalidDomainStateError


def test_valid_in_progress_recording() -> None:
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    recording = Recording(
        camera_id=uuid4(), file_path="/storage/recordings/a.mp4", started_at=started
    )
    assert recording.ended_at is None
    assert recording.duration_seconds is None


def test_valid_completed_recording_computes_duration() -> None:
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    ended = started + timedelta(seconds=90)
    recording = Recording(
        camera_id=uuid4(),
        file_path="/storage/recordings/a.mp4",
        started_at=started,
        ended_at=ended,
    )
    assert recording.duration_seconds == 90.0


def test_rejects_empty_file_path() -> None:
    with pytest.raises(InvalidDomainStateError):
        Recording(camera_id=uuid4(), file_path="  ", started_at=datetime.now(UTC))


def test_rejects_ended_before_started() -> None:
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    ended = started - timedelta(seconds=1)
    with pytest.raises(InvalidDomainStateError):
        Recording(camera_id=uuid4(), file_path="a.mp4", started_at=started, ended_at=ended)


def test_rejects_negative_size_bytes() -> None:
    with pytest.raises(InvalidDomainStateError):
        Recording(
            camera_id=uuid4(),
            file_path="a.mp4",
            started_at=datetime.now(UTC),
            size_bytes=-1,
        )
