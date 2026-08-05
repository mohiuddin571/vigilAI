from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.application.dto.camera_config import CameraConfigDTO, CameraConfigUpdate
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution


class CameraCreateRequest(BaseModel):
    """POST /cameras body. Deliberately excludes `name` — see M3 plan's Assumptions."""

    ip_address: str
    port: int = Field(default=80, gt=0, le=65535)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    rtsp_url_override: str | None = None

    @field_validator("rtsp_url_override")
    @classmethod
    def validate_rtsp_url_override(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.hostname:
            raise ValueError("RTSP URL override must be an rtsp:// or rtsps:// URL")
        return value


class CameraUpdateRequest(BaseModel):
    """PATCH /cameras/{id} body. Every field is optional — an omitted field is left at its
    current persisted value (`UpdateCameraUseCase`). Distinct from `CameraConfigUpdateRequest`
    (ONVIF encoder settings: resolution/codec/bitrate/fps) and `CameraRtspOverrideRequest`
    (the public RTSP override) — this is the camera's own identity/connection fields."""

    name: str | None = Field(default=None, min_length=1)
    ip_address: str | None = None
    port: int | None = Field(default=None, gt=0, le=65535)
    username: str | None = Field(default=None, min_length=1)
    password: str | None = Field(default=None, min_length=1)


class CameraRtspOverrideRequest(BaseModel):
    """Update only the optional public RTSP endpoint for an onboarded camera."""

    rtsp_url_override: str | None = None

    @field_validator("rtsp_url_override")
    @classmethod
    def validate_rtsp_url_override(cls, value: str | None) -> str | None:
        return CameraCreateRequest.validate_rtsp_url_override(value)


class StreamProfileResponse(BaseModel):
    id: UUID
    name: str
    resolution: str
    codec: str
    bitrate_kbps: int
    fps: int
    is_primary: bool
    onvif_token: str | None


class CameraResponse(BaseModel):
    """GET/POST /cameras response shape. Never includes the password (TD-15)."""

    id: UUID
    name: str
    ip_address: str
    port: int
    username: str
    rtsp_url_override: str | None
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
            rtsp_url_override=camera.rtsp_url_override,
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
                    onvif_token=profile.onvif_token,
                )
                for profile in camera.stream_profiles
            ],
        )


class VideoEncoderCapabilitiesResponse(BaseModel):
    """The camera-reported range of legal values for a profile's encoder config.

    Used by the frontend config panel to limit the edit form to fields/values
    the camera itself reports as supported (T-043) — codec is intentionally
    omitted here since it's not offered as editable (see
    docs/TECHNICAL_DECISIONS.md TD-19).
    """

    resolutions: list[str]
    fps_min: int
    fps_max: int
    bitrate_min_kbps: int | None
    bitrate_max_kbps: int | None


class CameraConfigResponse(BaseModel):
    """GET/PATCH /cameras/{id}/config response shape.

    `capabilities` is populated on GET (needed to build the limited edit
    form) and omitted on PATCH (the use case doesn't re-fetch it, since it
    doesn't change per-request and the frontend already has it from GET).
    """

    profile_id: str
    name: str
    resolution: str
    codec: str
    bitrate_kbps: int
    fps: int
    capabilities: VideoEncoderCapabilitiesResponse | None = None

    @classmethod
    def from_dto(cls, dto: CameraConfigDTO) -> "CameraConfigResponse":
        return cls(
            profile_id=dto.profile.onvif_token or "",
            name=dto.profile.name,
            resolution=str(dto.profile.resolution),
            codec=dto.profile.codec.value,
            bitrate_kbps=dto.profile.bitrate.value,
            fps=dto.profile.fps,
            capabilities=VideoEncoderCapabilitiesResponse(
                resolutions=[str(r) for r in dto.capabilities.resolutions],
                fps_min=dto.capabilities.fps_min,
                fps_max=dto.capabilities.fps_max,
                bitrate_min_kbps=dto.capabilities.bitrate_min_kbps,
                bitrate_max_kbps=dto.capabilities.bitrate_max_kbps,
            ),
        )

    @classmethod
    def from_profile(cls, profile: StreamProfile) -> "CameraConfigResponse":
        return cls(
            profile_id=profile.onvif_token or "",
            name=profile.name,
            resolution=str(profile.resolution),
            codec=profile.codec.value,
            bitrate_kbps=profile.bitrate.value,
            fps=profile.fps,
        )


class ResolutionUpdate(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class CameraConfigUpdateRequest(BaseModel):
    """PATCH /cameras/{id}/config body. Every field is optional — an omitted
    field is left at its current camera-reported value (see `CameraConfigUpdate`).
    """

    resolution: ResolutionUpdate | None = None
    codec: Codec | None = None
    bitrate_kbps: int | None = Field(default=None, gt=0)
    fps: int | None = Field(default=None, gt=0)

    def to_dto(self) -> CameraConfigUpdate:
        return CameraConfigUpdate(
            resolution=(
                Resolution(width=self.resolution.width, height=self.resolution.height)
                if self.resolution is not None
                else None
            ),
            codec=self.codec,
            bitrate=BitrateKbps(value=self.bitrate_kbps) if self.bitrate_kbps is not None else None,
            fps=self.fps,
        )
