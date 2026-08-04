from pydantic import BaseModel, ConfigDict, Field


class BitrateKbps(BaseModel):
    """An encoded stream data rate, in kilobits per second."""

    model_config = ConfigDict(frozen=True)

    value: int = Field(gt=0)

    def __str__(self) -> str:
        return f"{self.value}kbps"
