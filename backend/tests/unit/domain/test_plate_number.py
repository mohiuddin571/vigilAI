import pytest
from pydantic import ValidationError

from app.domain.value_objects.plate_number import PlateNumber


def test_normalizes_to_uppercase_and_strips() -> None:
    plate = PlateNumber(value="  abc123  ")
    assert plate.value == "ABC123"
    assert str(plate) == "ABC123"


def test_allows_spaces_and_hyphens_within_plate() -> None:
    plate = PlateNumber(value="ab-123 xy")
    assert plate.value == "AB-123 XY"


def test_rejects_empty_plate() -> None:
    with pytest.raises(ValidationError):
        PlateNumber(value="   ")


def test_rejects_invalid_characters() -> None:
    with pytest.raises(ValidationError):
        PlateNumber(value="ABC!23")


def test_rejects_non_string_value() -> None:
    with pytest.raises(ValidationError):
        PlateNumber(value=123)  # type: ignore[arg-type]
