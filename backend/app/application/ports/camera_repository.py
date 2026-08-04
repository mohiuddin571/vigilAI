from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.camera import Camera


class ICameraRepository(ABC):
    """Persists and retrieves onboarded cameras."""

    @abstractmethod
    async def add(self, camera: Camera) -> None: ...

    @abstractmethod
    async def get(self, camera_id: UUID) -> Camera | None: ...

    @abstractmethod
    async def list(self) -> list[Camera]: ...

    @abstractmethod
    async def update(self, camera: Camera) -> None: ...
