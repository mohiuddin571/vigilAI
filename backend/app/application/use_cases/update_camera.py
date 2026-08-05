from uuid import UUID

from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.camera import Camera
from app.domain.exceptions import CameraNotFoundError


class UpdateCameraUseCase:
    """Update an onboarded camera's identity/connection fields (name, IP, port,
    username, password) — every field is optional, an omitted field is left at its
    current persisted value, mirroring `UpdateZoneUseCase`'s partial-update shape.

    Deliberately does *not* re-authenticate against the camera over ONVIF (unlike
    `OnboardCameraUseCase`) — this is a quick correction of stored fields (a typo'd
    name, a camera that moved to a new IP on the same LAN), the same "plain field
    update, no re-validation" precedent `UpdateCameraRtspOverrideUseCase` already
    set for `rtsp_url_override`. If the new IP/credentials point at a different or
    unreachable device, that surfaces later as a `CameraUnreachableError`/
    `CameraAuthenticationError` the next time live view, recording, or analytics
    tries to use them — not synchronously here. An operator who needs the
    manufacturer/model/stream-profile info refreshed for a genuinely different
    physical camera should re-onboard it instead.

    Raises:
        CameraNotFoundError: no camera exists for `camera_id`.
    """

    def __init__(self, camera_repository: ICameraRepository) -> None:
        self._camera_repository = camera_repository

    async def execute(
        self,
        camera_id: UUID,
        name: str | None = None,
        ip_address: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> Camera:
        camera = await self._camera_repository.get(camera_id)
        if camera is None:
            raise CameraNotFoundError(f"No camera with id {camera_id}")
        # Reconstructed rather than mutated in place, mirroring
        # `UpdateZoneUseCase` — `Camera.__post_init__` validates name/
        # ip_address/username, so this is how that validation actually runs
        # on an edit instead of being silently bypassed by field assignment.
        updated = Camera(
            id=camera.id,
            name=name if name is not None else camera.name,
            ip_address=ip_address if ip_address is not None else camera.ip_address,
            username=username if username is not None else camera.username,
            port=port if port is not None else camera.port,
            password=password if password is not None else camera.password,
            rtsp_url_override=camera.rtsp_url_override,
            manufacturer=camera.manufacturer,
            model=camera.model,
            firmware_version=camera.firmware_version,
            stream_profiles=camera.stream_profiles,
            is_online=camera.is_online,
        )
        await self._camera_repository.update(updated)
        return updated
