import pytest
from pydantic import ValidationError

from app.domain.value_objects.bitrate import BitrateKbps


def test_valid_bitrate() -> None:
    bitrate = BitrateKbps(value=4096)
    assert bitrate.value == 4096
    assert str(bitrate) == "4096kbps"


@pytest.mark.parametrize("value", [0, -1, -100])
def test_rejects_non_positive_bitrate(value: int) -> None:
    with pytest.raises(ValidationError):
        BitrateKbps(value=value)
