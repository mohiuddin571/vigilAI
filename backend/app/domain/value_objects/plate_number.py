import re

from pydantic import BaseModel, ConfigDict, field_validator

_PLATE_PATTERN = re.compile(r"^[A-Z0-9](?:[A-Z0-9 -]{0,10}[A-Z0-9])?$")


class PlateNumber(BaseModel):
    """A recognized license plate string, normalized for comparison/storage."""

    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("value", mode="after")
    @classmethod
    def _check_format(cls, value: str) -> str:
        if not _PLATE_PATTERN.match(value):
            raise ValueError(f"{value!r} is not a valid plate number")
        return value

    def __str__(self) -> str:
        return self.value
