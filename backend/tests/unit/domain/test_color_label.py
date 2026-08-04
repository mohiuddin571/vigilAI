import pytest

from app.domain.value_objects.color_label import ColorLabel


def test_valid_members() -> None:
    assert ColorLabel.RED == "red"
    assert ColorLabel("blue") is ColorLabel.BLUE


def test_rejects_unknown_color() -> None:
    with pytest.raises(ValueError, match="magenta"):
        ColorLabel("magenta")
