import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import numpy as np
import pytest

from app.application.ports.camera_repository import ICameraRepository
from app.application.use_cases.analytics_session_registry import AnalyticsSessionRegistry
from app.application.use_cases.run_analytics_pipeline import RunAnalyticsPipelineUseCase
from app.application.use_cases.update_camera_analytics_settings import (
    UpdateCameraAnalyticsSettingsUseCase,
)
from app.domain.entities.camera import Camera
from app.domain.entities.detection_event import DetectionEvent
from app.domain.entities.frame import Frame
from app.domain.exceptions import CameraNotFoundError, InvalidDomainStateError

_KNOWN_TYPES = frozenset({"yolo_object_detector", "color_detector", "loitering_detector"})


async def _fail_build_use_case(source_id: str) -> RunAnalyticsPipelineUseCase:
    raise AssertionError("build_use_case must not be called: no session is running")


def _make_registry() -> AnalyticsSessionRegistry:
    """A registry with no running sessions — `restart()` on it is always a
    no-op, matching every test below except the one that explicitly enables
    a session first to assert `restart()` is actually triggered."""
    return AnalyticsSessionRegistry(_fail_build_use_case)


class _LoopingSource:
    """Yields frames forever (unlike `frame_count`-bounded fakes elsewhere) so
    `request_stop()` is guaranteed to be observed on the next loop iteration
    instead of the fake blocking indefinitely on an exhausted generator."""

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def frames(self) -> AsyncIterator[Frame]:
        sequence = 0
        while True:
            yield Frame(
                source_id=self.source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=np.zeros((2, 2, 3), dtype=np.uint8),
            )
            sequence += 1
            await asyncio.sleep(0)


class _NoopEventPublisher:
    async def publish(self, event: DetectionEvent) -> None:
        pass

    def subscribe(self, handler: object) -> None:  # pragma: no cover - unused here
        raise NotImplementedError


class FakeCameraRepository(ICameraRepository):
    def __init__(self, cameras: list[Camera] | None = None) -> None:
        self.cameras: dict[UUID, Camera] = {camera.id: camera for camera in cameras or []}

    async def add(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera

    async def get(self, camera_id: UUID) -> Camera | None:
        return self.cameras.get(camera_id)

    async def list(self) -> list[Camera]:
        return list(self.cameras.values())

    async def update(self, camera: Camera) -> None:
        self.cameras[camera.id] = camera

    async def delete(self, camera_id: UUID) -> None:
        self.cameras.pop(camera_id, None)


def _make_camera(**overrides: object) -> Camera:
    defaults: dict[str, object] = {
        "name": "Front Door",
        "ip_address": "10.0.0.5",
        "username": "admin",
    }
    defaults.update(overrides)
    return Camera(**defaults)  # type: ignore[arg-type]


async def test_update_analytics_settings_persists_the_enabled_subset() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraAnalyticsSettingsUseCase(
        repository, known_detector_types=_KNOWN_TYPES, analytics_session_registry=_make_registry()
    )

    updated = await use_case.execute(
        camera.id, enabled_detector_types=frozenset({"color_detector"})
    )

    assert updated.enabled_detector_types == frozenset({"color_detector"})
    assert repository.cameras[camera.id].enabled_detector_types == frozenset({"color_detector"})


async def test_update_analytics_settings_none_means_all_enabled() -> None:
    camera = _make_camera(enabled_detector_types=frozenset({"color_detector"}))
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraAnalyticsSettingsUseCase(
        repository, known_detector_types=_KNOWN_TYPES, analytics_session_registry=_make_registry()
    )

    updated = await use_case.execute(camera.id, enabled_detector_types=None)

    assert updated.enabled_detector_types is None


async def test_update_analytics_settings_empty_set_disables_every_type() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraAnalyticsSettingsUseCase(
        repository, known_detector_types=_KNOWN_TYPES, analytics_session_registry=_make_registry()
    )

    updated = await use_case.execute(camera.id, enabled_detector_types=frozenset())

    assert updated.enabled_detector_types == frozenset()


async def test_update_analytics_settings_rejects_unknown_type() -> None:
    camera = _make_camera()
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraAnalyticsSettingsUseCase(
        repository, known_detector_types=_KNOWN_TYPES, analytics_session_registry=_make_registry()
    )

    with pytest.raises(InvalidDomainStateError):
        await use_case.execute(camera.id, enabled_detector_types=frozenset({"not_a_real_plugin"}))


async def test_update_analytics_settings_raises_not_found_for_unknown_camera() -> None:
    use_case = UpdateCameraAnalyticsSettingsUseCase(
        FakeCameraRepository(),
        known_detector_types=_KNOWN_TYPES,
        analytics_session_registry=_make_registry(),
    )

    with pytest.raises(CameraNotFoundError):
        await use_case.execute(uuid4(), enabled_detector_types=None)


async def test_update_analytics_settings_preserves_other_camera_fields() -> None:
    camera = _make_camera(manufacturer="Acme", model="X100", is_online=True)
    repository = FakeCameraRepository([camera])
    use_case = UpdateCameraAnalyticsSettingsUseCase(
        repository, known_detector_types=_KNOWN_TYPES, analytics_session_registry=_make_registry()
    )

    updated = await use_case.execute(
        camera.id, enabled_detector_types=frozenset({"loitering_detector"})
    )

    assert updated.manufacturer == "Acme"
    assert updated.model == "X100"
    assert updated.is_online is True


async def test_update_analytics_settings_restarts_an_already_running_session() -> None:
    """The bug this closes: a camera whose analytics session was already
    running when its `enabled_detector_types` changed used to keep running
    with the plugin set it was originally built with, silently ignoring the
    new setting until the whole backend process restarted."""
    camera = _make_camera()
    repository = FakeCameraRepository([camera])
    sources: list[_LoopingSource] = []

    async def build_use_case(source_id: str) -> RunAnalyticsPipelineUseCase:
        source = _LoopingSource(source_id)
        sources.append(source)
        return RunAnalyticsPipelineUseCase(
            source,  # type: ignore[arg-type]
            lambda frame: _async_empty(),
            _NoopEventPublisher(),  # type: ignore[arg-type]
        )

    registry = AnalyticsSessionRegistry(build_use_case)
    await registry.enable(str(camera.id))
    assert len(sources) == 1

    use_case = UpdateCameraAnalyticsSettingsUseCase(
        repository, known_detector_types=_KNOWN_TYPES, analytics_session_registry=registry
    )
    await use_case.execute(camera.id, enabled_detector_types=frozenset({"color_detector"}))
    for _ in range(1000):
        if sources[-1].start_calls:
            break
        await asyncio.sleep(0)

    # A second session was built (the settings change took effect
    # immediately) and the first session's source was stopped, not leaked.
    assert len(sources) == 2
    assert sources[0].stop_calls == 1
    assert sources[1].start_calls == 1
    assert registry.is_enabled(str(camera.id)) is True


async def _async_empty() -> list[DetectionEvent]:
    return []
