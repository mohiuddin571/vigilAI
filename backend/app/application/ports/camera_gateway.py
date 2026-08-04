from abc import ABC, abstractmethod

from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile


class ICameraGateway(ABC):
    """Talks to a physical camera over its device protocol (e.g. ONVIF).

    Implemented by `infrastructure/onvif/OnvifCameraGateway` starting at M3.
    """

    @abstractmethod
    async def connect(self, ip_address: str, username: str, password: str) -> None:
        """Authenticate against the camera. Raises CameraUnreachableError on failure."""

    @abstractmethod
    async def get_device_info(self) -> Camera:
        """Fetch manufacturer/model/firmware info as a partially-populated Camera."""

    @abstractmethod
    async def get_profiles(self) -> list[StreamProfile]:
        """Fetch every stream profile the camera reports."""

    @abstractmethod
    async def get_video_encoder_configuration(self, profile_id: str) -> StreamProfile:
        """Read the current resolution/fps/bitrate/codec for one profile."""

    @abstractmethod
    async def set_video_encoder_configuration(
        self, profile_id: str, profile: StreamProfile
    ) -> None:
        """Apply a new encoder configuration.

        Raises UnsupportedConfigurationError if the camera rejects the change.
        """

    @abstractmethod
    async def get_stream_uri(self, profile_id: str) -> str:
        """Resolve a profile to its RTSP stream URL."""
