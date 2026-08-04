from uuid import UUID

from app.application.dto.camera_config import CameraConfigUpdate
from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import CameraNotFoundError


class UpdateCameraConfigUseCase:
    """Update a camera's resolution/FPS/bitrate for one stream profile.

    Preconditions: `camera_id` identifies a previously onboarded camera;
    `profile_id` matches one of its persisted stream profiles' `onvif_token`;
    `updates` carries only the fields being changed (unset fields keep their
    current live value — see `CameraConfigUpdate`).

    Postconditions: the camera's encoder configuration is updated on the
    device and the persisted `Camera`/`StreamProfile` reflects the change.

    Raises:
        CameraNotFoundError: no such camera, or no such profile on it.
        CameraUnreachableError: the camera could not be reached.
        UnsupportedConfigurationError: the camera rejects the requested
            change — a field/value it does not report as supported (never
            silently ignored).
    """

    def __init__(
        self, camera_gateway: ICameraGateway, camera_repository: ICameraRepository
    ) -> None:
        self._camera_gateway = camera_gateway
        self._camera_repository = camera_repository

    async def execute(
        self, camera_id: UUID, profile_id: str, updates: CameraConfigUpdate
    ) -> StreamProfile:
        camera = await self._camera_repository.get(camera_id)
        if camera is None:
            raise CameraNotFoundError(f"No camera with id {camera_id}")
        persisted_profile = next(
            (p for p in camera.stream_profiles if p.onvif_token == profile_id), None
        )
        if persisted_profile is None:
            raise CameraNotFoundError(f"No stream profile {profile_id!r} for camera {camera_id}")

        try:
            await self._camera_gateway.connect(
                camera.ip_address, camera.username, camera.password, camera.port
            )
            current = await self._camera_gateway.get_video_encoder_configuration(profile_id)
            desired = StreamProfile(
                id=persisted_profile.id,
                name=current.name,
                resolution=updates.resolution or current.resolution,
                codec=updates.codec or current.codec,
                bitrate=updates.bitrate or current.bitrate,
                fps=updates.fps if updates.fps is not None else current.fps,
                is_primary=persisted_profile.is_primary,
                onvif_token=profile_id,
            )
            await self._camera_gateway.set_video_encoder_configuration(profile_id, desired)
            updated = await self._camera_gateway.get_video_encoder_configuration(profile_id)
        finally:
            await self._camera_gateway.disconnect()

        result = StreamProfile(
            id=persisted_profile.id,
            name=updated.name,
            resolution=updated.resolution,
            codec=updated.codec,
            bitrate=updated.bitrate,
            fps=updated.fps,
            is_primary=persisted_profile.is_primary,
            onvif_token=profile_id,
        )
        camera.stream_profiles = [
            result if p.id == persisted_profile.id else p for p in camera.stream_profiles
        ]
        await self._camera_repository.update(camera)
        return result
