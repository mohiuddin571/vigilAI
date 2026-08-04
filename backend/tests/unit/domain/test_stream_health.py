from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.value_objects.stream_health import StreamHealth, StreamState


def test_defaults() -> None:
    health = StreamHealth(state=StreamState.CONNECTING)
    assert health.last_frame_at is None
    assert health.consecutive_failures == 0
    assert health.last_error is None


def test_is_frozen() -> None:
    health = StreamHealth(state=StreamState.CONNECTED, last_frame_at=datetime.now(UTC))
    with pytest.raises(ValidationError):
        health.state = StreamState.FAILED
