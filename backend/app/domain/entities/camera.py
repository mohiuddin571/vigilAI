import ipaddress
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import InvalidDomainStateError


@dataclass
class Camera:
    """An onboarded camera and the stream profiles it reports."""

    name: str
    ip_address: str
    username: str
    id: UUID = field(default_factory=uuid4)
    port: int = 80
    password: str = field(default="", repr=False)
    rtsp_url_override: str | None = field(default=None, repr=False)
    manufacturer: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    stream_profiles: list[StreamProfile] = field(default_factory=list)
    is_online: bool = False
    # `None` means every known detector plugin is enabled — the default for
    # every camera until its analytics settings are explicitly changed
    # (`UpdateCameraAnalyticsSettingsUseCase`). An empty frozenset means all
    # types are explicitly disabled, distinct from `None`.
    enabled_detector_types: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidDomainStateError("Camera name must not be empty")
        try:
            ipaddress.ip_address(self.ip_address)
        except ValueError as exc:
            raise InvalidDomainStateError(f"{self.ip_address!r} is not a valid IP address") from exc
        if not self.username.strip():
            raise InvalidDomainStateError("Camera username must not be empty")
