from pydantic import BaseModel, ConfigDict, Field


class Resolution(BaseModel):
    """A video frame resolution in pixels."""

    model_config = ConfigDict(frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"
