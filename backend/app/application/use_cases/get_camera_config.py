from uuid import UUID

from app.application.dto.camera_config import CameraConfigDTO
from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.domain.exceptions import CameraNotFoundError


class GetCameraConfigUseCase:
    """Read a camera's live video-encoder configuration and its capabilities.

    Preconditions: `camera_id` identifies a previously onboarded camera, and
    `profile_id` matches one of its persisted stream profiles' `onvif_token`.

    Postconditions: none — this is a pure read. Both the returned current
    values and capabilities always come from a live ONVIF call, never from
    `Camera.stream_profiles`.

    Raises:
        CameraNotFoundError: no such camera, or no such profile on it.
        CameraUnreachableError: the camera could not be reached.
        UnsupportedConfigurationError: the camera reported a configuration
            this system cannot interpret (see docs/TECHNICAL_DECISIONS.md TD-18).
    """

    def __init__(
        self, camera_gateway: ICameraGateway, camera_repository: ICameraRepository
    ) -> None:
        self._camera_gateway = camera_gateway
        self._camera_repository = camera_repository

    async def execute(self, camera_id: UUID, profile_id: str) -> CameraConfigDTO:
        camera = await self._camera_repository.get(camera_id)
        if camera is None:
            raise CameraNotFoundError(f"No camera with id {camera_id}")
        if not any(profile.onvif_token == profile_id for profile in camera.stream_profiles):
            raise CameraNotFoundError(f"No stream profile {profile_id!r} for camera {camera_id}")

        try:
            await self._camera_gateway.connect(
                camera.ip_address, camera.username, camera.password, camera.port
            )
            profile = await self._camera_gateway.get_video_encoder_configuration(profile_id)
            capabilities = await self._camera_gateway.get_video_encoder_configuration_options(
                profile_id
            )
        finally:
            await self._camera_gateway.disconnect()

        return CameraConfigDTO(profile=profile, capabilities=capabilities)
