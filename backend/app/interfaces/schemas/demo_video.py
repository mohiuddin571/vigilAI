from pydantic import BaseModel

from app.domain.entities.demo_video import DemoVideo


class DemoVideoResponse(BaseModel):
    """Response shape for one entry in `GET /demo/videos` (M17)."""

    id: str
    filename: str

    @classmethod
    def from_domain(cls, video: DemoVideo) -> "DemoVideoResponse":
        return cls(id=video.id, filename=video.filename)
