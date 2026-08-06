from uuid import UUID

from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.analytics_session_registry import AnalyticsSessionRegistry
from app.domain.entities.camera import Camera
from app.domain.exceptions import CameraNotFoundError, InvalidDomainStateError


class UpdateCameraAnalyticsSettingsUseCase:
    """Persist which detector plugin types run for one camera's analytics pipeline.

    `enabled_detector_types=None` means every known type stays enabled — the
    same `None`-means-all semantics `Camera.enabled_detector_types` and
    `AnalyticsOrchestrator.process`'s `enabled_plugin_ids` parameter both use.
    Persisting the change alone isn't enough, though: `enabled_plugin_ids` is
    resolved once, at session-build time (`Container._build_analytics_use_case`),
    and `AnalyticsSessionRegistry.enable()` reuses an already-running session
    verbatim rather than re-resolving it — so this use case also calls
    `AnalyticsSessionRegistry.restart()` for this camera, which is a no-op if
    no session is currently running (nothing to pick the new settings up
    until analytics is next enabled) and otherwise tears down and rebuilds
    the running session in place so the new detector set applies immediately
    (see `AnalyticsSessionRegistry.restart`'s docstring).

    Raises:
        CameraNotFoundError: no camera exists for `camera_id`.
        InvalidDomainStateError: `enabled_detector_types` names a type outside
            `known_detector_types` (a typo, or a plugin id that no longer exists).
    """

    def __init__(
        self,
        camera_repository: ICameraRepository,
        known_detector_types: frozenset[str],
        analytics_session_registry: AnalyticsSessionRegistry,
    ) -> None:
        self._camera_repository = camera_repository
        self._known_detector_types = known_detector_types
        self._analytics_session_registry = analytics_session_registry

    async def execute(
        self, camera_id: UUID, enabled_detector_types: frozenset[str] | None
    ) -> Camera:
        camera = await self._camera_repository.get(camera_id)
        if camera is None:
            raise CameraNotFoundError(f"No camera with id {camera_id}")
        if enabled_detector_types is not None:
            unknown = enabled_detector_types - self._known_detector_types
            if unknown:
                raise InvalidDomainStateError(f"Unknown detector type(s): {sorted(unknown)}")
        camera.enabled_detector_types = enabled_detector_types
        await self._camera_repository.update(camera)
        await self._analytics_session_registry.restart(str(camera.id))
        return camera
