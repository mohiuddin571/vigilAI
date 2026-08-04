import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.camera_repository import ICameraRepository
from app.domain.entities.camera import Camera
from app.domain.entities.stream_profile import StreamProfile
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.infrastructure.persistence.models import CameraRow
from app.infrastructure.security.credential_cipher import CredentialCipher


def _profile_to_dict(profile: StreamProfile) -> dict[str, Any]:
    return {
        "id": str(profile.id),
        "name": profile.name,
        "resolution": {"width": profile.resolution.width, "height": profile.resolution.height},
        "codec": profile.codec.value,
        "bitrate": profile.bitrate.value,
        "fps": profile.fps,
        "is_primary": profile.is_primary,
        "onvif_token": profile.onvif_token,
    }


def _profile_from_dict(data: dict[str, Any]) -> StreamProfile:
    resolution: dict[str, Any] = data["resolution"]
    onvif_token = data["onvif_token"]
    return StreamProfile(
        id=UUID(str(data["id"])),
        name=str(data["name"]),
        resolution=Resolution(width=int(resolution["width"]), height=int(resolution["height"])),
        codec=Codec(str(data["codec"])),
        bitrate=BitrateKbps(value=int(data["bitrate"])),
        fps=int(data["fps"]),
        is_primary=bool(data["is_primary"]),
        onvif_token=str(onvif_token) if onvif_token is not None else None,
    )


class SqlCameraRepository(ICameraRepository):
    """`ICameraRepository` backed by SQLModel/SQLite (TD-09).

    The only repository responsibility beyond plain CRUD: encrypting/decrypting
    the camera password at the SQL-row boundary (TD-15) via `CredentialCipher` —
    `Camera.password` is plaintext everywhere else in the application.
    """

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], cipher: CredentialCipher
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    async def add(self, camera: Camera) -> None:
        row = self._to_row(camera)
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def get(self, camera_id: UUID) -> Camera | None:
        async with self._session_factory() as session:
            row = await session.get(CameraRow, str(camera_id))
            return self._to_entity(row) if row is not None else None

    async def list(self) -> list[Camera]:
        async with self._session_factory() as session:
            result = await session.execute(select(CameraRow))
            return [self._to_entity(row) for row in result.scalars().all()]

    async def update(self, camera: Camera) -> None:
        row = self._to_row(camera)
        async with self._session_factory() as session:
            await session.merge(row)
            await session.commit()

    def _to_row(self, camera: Camera) -> CameraRow:
        return CameraRow(
            id=str(camera.id),
            name=camera.name,
            ip_address=camera.ip_address,
            port=camera.port,
            username=camera.username,
            encrypted_password=self._cipher.encrypt(camera.password),
            manufacturer=camera.manufacturer,
            model=camera.model,
            firmware_version=camera.firmware_version,
            is_online=camera.is_online,
            stream_profiles_json=json.dumps([_profile_to_dict(p) for p in camera.stream_profiles]),
        )

    def _to_entity(self, row: CameraRow) -> Camera:
        return Camera(
            id=UUID(row.id),
            name=row.name,
            ip_address=row.ip_address,
            port=row.port,
            username=row.username,
            password=self._cipher.decrypt(row.encrypted_password),
            manufacturer=row.manufacturer,
            model=row.model,
            firmware_version=row.firmware_version,
            is_online=row.is_online,
            stream_profiles=[_profile_from_dict(d) for d in json.loads(row.stream_profiles_json)],
        )
