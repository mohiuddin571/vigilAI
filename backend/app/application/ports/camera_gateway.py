from abc import ABC, abstractmethod

from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities


class ICameraGateway(ABC):
    """Talks to a physical camera over its device protocol (e.g. ONVIF).

    Implemented by `infrastructure/onvif/OnvifCameraGateway` starting at M3.
    """

    @abstractmethod
    async def connect(self, ip_address: str, username: str, password: str, port: int = 80) -> None:
        """Authenticate against the camera.

        Raises CameraAuthenticationError if the credentials are rejected, or
        CameraUnreachableError if the camera cannot be reached at all.
        """

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

        Raises UnsupportedConfigurationError if the camera rejects the change,
        including a requested field/value the camera's own profile does not
        report as supported (see `get_video_encoder_configuration_options`).
        """

    @abstractmethod
    async def get_video_encoder_configuration_options(
        self, profile_id: str
    ) -> VideoEncoderCapabilities:
        """Fetch the camera-reported range of legal encoder values for one profile.

        Added at M4 (docs/TECHNICAL_DECISIONS.md TD-19): callers (e.g. the
        config API) use this to limit what's offered as editable, rather than
        letting a client discover unsupported fields only by trial and error.
        """

    @abstractmethod
    async def get_stream_uri(self, profile_id: str) -> str:
        """Resolve a profile to its RTSP stream URL."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Release any resources held by an open connection.

        Safe to call even if `connect` was never called, or failed.
        """
