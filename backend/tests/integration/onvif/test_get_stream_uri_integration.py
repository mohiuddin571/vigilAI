"""T-050: `OnvifCameraGateway.get_stream_uri` against the fixture-driven fake ONVIF client.

`GetStreamUri` is the control-plane call `OnvifRtspFrameSource` depends on to
resolve an RTSP URL — never the pixel path itself (docs/ARCHITECTURE.md §5).
"""

import functools

import pytest

from app.domain.exceptions import CameraAuthenticationError, CameraUnreachableError
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from tests.fixtures.onvif.fake_camera import FakeOnvifCamera


async def test_get_stream_uri_returns_the_camera_reported_uri() -> None:
    gateway = OnvifCameraGateway(client_factory=FakeOnvifCamera)
    await gateway.connect("10.0.0.5", "admin", "s3cret-pass", 8000)

    uri = await gateway.get_stream_uri("Profile_1")

    assert uri == "rtsp://camera.invalid:554/stream1"
    await gateway.disconnect()


async def test_connect_enables_nat_override_for_private_camera_xaddrs() -> None:
    created_clients: list[FakeOnvifCamera] = []

    def client_factory(*args: object, **kwargs: object) -> FakeOnvifCamera:
        client = FakeOnvifCamera(*args, **kwargs)  # type: ignore[arg-type]
        created_clients.append(client)
        return client

    gateway = OnvifCameraGateway(client_factory=client_factory)
    await gateway.connect("154.210.224.77", "admin", "s3cret-pass", 7008)

    assert len(created_clients) == 1
    assert created_clients[0].host == "154.210.224.77"
    assert created_clients[0].port == 7008
    assert created_clients[0].nat_override is True
    await gateway.disconnect()


async def test_get_stream_uri_reflects_the_fake_cameras_configured_uri() -> None:
    client_factory = functools.partial(
        FakeOnvifCamera, stream_uri="rtsp://10.0.0.5:554/onvif/profile1/media.smp"
    )
    gateway = OnvifCameraGateway(client_factory=client_factory)
    await gateway.connect("10.0.0.5", "admin", "s3cret-pass", 8000)

    uri = await gateway.get_stream_uri("Profile_1")

    assert uri == "rtsp://10.0.0.5:554/onvif/profile1/media.smp"
    await gateway.disconnect()


async def test_get_stream_uri_requires_a_prior_connect() -> None:
    gateway = OnvifCameraGateway(client_factory=FakeOnvifCamera)
    with pytest.raises(CameraUnreachableError):
        await gateway.get_stream_uri("Profile_1")


async def test_get_stream_uri_propagates_a_classified_auth_failure() -> None:
    client_factory = functools.partial(FakeOnvifCamera, fail_with=Exception("Password Mismatch"))
    gateway = OnvifCameraGateway(client_factory=client_factory)

    with pytest.raises(CameraAuthenticationError):
        await gateway.connect("10.0.0.5", "admin", "wrong-pass", 8000)
