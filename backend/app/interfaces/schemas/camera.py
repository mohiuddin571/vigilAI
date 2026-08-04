from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.camera import Camera


class CameraCreateRequest(BaseModel):
    """POST /cameras body. Deliberately excludes `name` — see M3 plan's Assumptions."""

    ip_address: str
    port: int = Field(default=80, gt=0, le=65535)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class StreamProfileResponse(BaseModel):
    id: UUID
    name: str
    resolution: str
    codec: str
    bitrate_kbps: int
    fps: int
    is_primary: bool


class CameraResponse(BaseModel):
    """GET/POST /cameras response shape. Never includes the password (TD-15)."""

    id: UUID
    name: str
    ip_address: str
    port: int
    username: str
    manufacturer: str | None
    model: str | None
    firmware_version: str | None
    is_online: bool
    stream_profiles: list[StreamProfileResponse]

    @classmethod
    def from_domain(cls, camera: Camera) -> "CameraResponse":
        return cls(
            id=camera.id,
            name=camera.name,
            ip_address=camera.ip_address,
            port=camera.port,
            username=camera.username,
            manufacturer=camera.manufacturer,
            model=camera.model,
            firmware_version=camera.firmware_version,
            is_online=camera.is_online,
            stream_profiles=[
                StreamProfileResponse(
                    id=profile.id,
                    name=profile.name,
                    resolution=str(profile.resolution),
                    codec=profile.codec.value,
                    bitrate_kbps=profile.bitrate.value,
                    fps=profile.fps,
                    is_primary=profile.is_primary,
                )
                for profile in camera.stream_profiles
            ],
        )
