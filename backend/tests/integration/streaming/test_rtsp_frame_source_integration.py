"""Integration tests for `RawRtspFrameSource`/`OnvifRtspFrameSource` (T-050/T-051).

Neither a physical camera nor a local RTSP test server is available in this
environment (no evaluator camera, and `ffmpeg`/an RTSP server binary aren't
installed here — see docs/TECHNICAL_DECISIONS.md TD-21's "known limitation"
entry, mirroring TD-18/TD-20's precedent of documenting rather than faking
hardware-dependent coverage). What *is* verifiable without either: both
classes share the exact `cv2.VideoCapture`-based decode call shape
`Mp4FileFrameSource` uses (T-050's DoD: "Same `Frame` shape as
`Mp4FileFrameSource`") — `cv2.VideoCapture` opens the committed MP4 fixture
path identically to how it would open an `rtsp://` URL, so pointing
`RawRtspFrameSource` at the fixture path exercises the real decode code path
end to end, without a real network source.

A real-camera/local-RTSP-server run of T-054's reconnect scenario remains a
`@pytest.mark.hardware`-gated manual step, documented in TASKS.md/TD-21, not
simulated here.
"""

import functools
from pathlib import Path

import pytest

from app.domain.exceptions import FrameSourceUnavailableError
from app.infrastructure.onvif.onvif_camera_gateway import OnvifCameraGateway
from app.infrastructure.streaming.rtsp_frame_source import (
    OnvifRtspFrameSource,
    RawRtspFrameSource,
    _add_rtsp_credentials,
)
from tests.fixtures.onvif.fake_camera import FakeOnvifCamera

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"
_FIXTURE_FRAME_SHAPE = (240, 320, 3)


def test_rtsp_override_adds_camera_credentials_without_replacing_explicit_ones() -> None:
    assert (
        _add_rtsp_credentials("rtsp://public.example:8008/unicaststream/1", "test", "password@123")
        == "rtsp://test:password%40123@public.example:8008/unicaststream/1"
    )
    assert (
        _add_rtsp_credentials(
            "rtsp://other:secret@public.example:8008/unicaststream/1", "test", "password"
        )
        == "rtsp://other:secret@public.example:8008/unicaststream/1"
    )


async def test_raw_rtsp_frame_source_yields_frames_with_the_mp4_frame_source_shape() -> None:
    source = RawRtspFrameSource(str(_FIXTURE_PATH), source_id="raw-rtsp-test")
    await source.start()
    try:
        frames = source.frames()
        collected = [await anext(frames) for _ in range(3)]
    finally:
        await source.stop()

    assert [f.sequence for f in collected] == [0, 1, 2]
    for frame in collected:
        assert frame.source_id == "raw-rtsp-test"
        assert frame.image.shape == _FIXTURE_FRAME_SHAPE


async def test_raw_rtsp_frame_source_ends_iteration_at_end_of_stream_no_looping() -> None:
    source = RawRtspFrameSource(str(_FIXTURE_PATH), source_id="raw-rtsp-eof")
    await source.start()
    try:
        collected = [frame async for frame in source.frames()]
    finally:
        await source.stop()

    assert len(collected) == 50  # matches the fixture's frame count (T-021)


async def test_raw_rtsp_frame_source_raises_frame_source_unavailable_for_a_bad_url() -> None:
    source = RawRtspFrameSource("/nonexistent/does-not-exist.mp4", source_id="raw-rtsp-missing")
    with pytest.raises(FrameSourceUnavailableError):
        await source.start()


def _fake_gateway_factory(
    stream_uri: str, built: list[OnvifCameraGateway]
) -> functools.partial[OnvifCameraGateway]:
    client_factory = functools.partial(FakeOnvifCamera, stream_uri=stream_uri)

    def factory() -> OnvifCameraGateway:
        gateway = OnvifCameraGateway(client_factory=client_factory)
        built.append(gateway)
        return gateway

    return factory  # type: ignore[return-value]


async def test_onvif_rtsp_frame_source_resolves_uri_then_decodes_it() -> None:
    """`OnvifRtspFrameSource` resolves `GetStreamUri` via a fake gateway, then
    opens *that* URI — pointed at the local fixture path so the resolve step
    is real while the "network" URL is actually a local file, proving the
    control-plane/pixel-plane split works end to end without a real camera.
    """
    built: list[OnvifCameraGateway] = []
    source = OnvifRtspFrameSource(
        ip_address="10.0.0.5",
        username="admin",
        password="s3cret-pass",
        profile_id="Profile_1",
        source_id="onvif-rtsp-test",
        camera_gateway_factory=_fake_gateway_factory(str(_FIXTURE_PATH), built),
        port=8000,
    )
    await source.start()
    try:
        frame = await anext(source.frames())
    finally:
        await source.stop()

    assert frame.source_id == "onvif-rtsp-test"
    assert frame.image.shape == _FIXTURE_FRAME_SHAPE


async def test_onvif_rtsp_frame_source_builds_exactly_one_gateway_per_start() -> None:
    built: list[OnvifCameraGateway] = []
    source = OnvifRtspFrameSource(
        ip_address="10.0.0.5",
        username="admin",
        password="s3cret-pass",
        profile_id="Profile_1",
        source_id="onvif-rtsp-gateway-count-test",
        camera_gateway_factory=_fake_gateway_factory(str(_FIXTURE_PATH), built),
    )
    await source.start()
    await source.stop()

    assert len(built) == 1


async def test_onvif_rtsp_frame_source_uses_the_public_rtsp_override() -> None:
    built: list[OnvifCameraGateway] = []
    source = OnvifRtspFrameSource(
        ip_address="10.0.0.5",
        username="admin",
        password="s3cret-pass",
        profile_id="Profile_1",
        source_id="onvif-rtsp-override-test",
        camera_gateway_factory=_fake_gateway_factory("/nonexistent/camera-uri", built),
        rtsp_url_override=str(_FIXTURE_PATH),
    )
    await source.start()
    try:
        frame = await anext(source.frames())
    finally:
        await source.stop()

    assert frame.source_id == "onvif-rtsp-override-test"
    assert built == []


async def test_onvif_rtsp_frame_source_raises_frame_source_unavailable_for_a_bad_uri() -> None:
    built: list[OnvifCameraGateway] = []
    source = OnvifRtspFrameSource(
        ip_address="10.0.0.5",
        username="admin",
        password="s3cret-pass",
        profile_id="Profile_1",
        source_id="onvif-rtsp-bad-uri-test",
        camera_gateway_factory=_fake_gateway_factory("/nonexistent/does-not-exist.mp4", built),
    )
    with pytest.raises(FrameSourceUnavailableError):
        await source.start()
