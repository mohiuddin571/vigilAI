import asyncio
import os
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from urllib.parse import quote, urlparse, urlunparse

import cv2

from app.application.ports.camera_gateway import ICameraGateway
from app.application.ports.frame_source import IFrameSource
from app.domain.entities.frame import Frame
from app.domain.exceptions import DomainError, FrameSourceUnavailableError


def _open_capture(
    url: str, open_timeout_ms: int, read_timeout_ms: int, rtsp_transport: str
) -> cv2.VideoCapture:
    """Open an RTSP (or any FFmpeg-readable) URL via OpenCV's bundled FFmpeg backend.

    This is the same `cv2.VideoCapture`-based decode path `Mp4FileFrameSource`
    uses (TD-04/TD-20), just pointed at a network URL instead of a local file
    (docs/ARCHITECTURE.md §5: "delegates actual pixel decoding to the same
    FFmpeg/OpenCV pipeline"). The `params` overload (OpenCV 4.5.3+) sets
    open/read timeouts so a dead RTSP source fails fast instead of hanging
    the child process indefinitely.
    """
    # OpenCV exposes FFmpeg's RTSP transport option through this process-local
    # environment variable, not through the VideoCapture parameter API. This
    # value comes from Settings via constructor injection; it is never read
    # from the environment in this adapter.
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{rtsp_transport}"
    return cv2.VideoCapture(
        url,
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            open_timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            read_timeout_ms,
        ],
    )


def _add_rtsp_credentials(url: str, username: str, password: str) -> str:
    """Add stored camera credentials to an override URL that has none.

    ONVIF often returns an authenticated RTSP URI, while a manually entered
    public override generally does not. Do not replace credentials explicitly
    provided in the override, and leave non-URL fixture paths untouched.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"rtsp", "rtsps"} or parsed.hostname is None or parsed.username:
        return url
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    credentials = f"{quote(username, safe='')}:{quote(password, safe='')}"
    return urlunparse(parsed._replace(netloc=f"{credentials}@{host}{port}"))


async def _frames_from_capture(cap: cv2.VideoCapture, source_id: str) -> AsyncIterator[Frame]:
    """Read frames from an already-opened capture until the stream ends/drops.

    No looping and no FPS throttling, unlike `Mp4FileFrameSource`: RTSP is a
    live source already paced by the network, and a genuine end-of-stream
    here means disconnect, not "restart from the top" — `ReconnectSupervisor`
    (source-agnostic, unchanged) is what turns this into a reconnect attempt.
    """
    sequence = 0
    while True:
        ok, image = await asyncio.to_thread(cap.read)
        if not ok:
            return
        yield Frame(
            source_id=source_id,
            sequence=sequence,
            timestamp=datetime.now(UTC),
            image=image,
        )
        sequence += 1


class RawRtspFrameSource(IFrameSource):
    """Connects directly to a caller-supplied RTSP (or other FFmpeg-readable) URL.

    No ONVIF involved (T-051) — exists so the system works against generic
    RTSP streams that were never ONVIF-onboarded, and so the shared decode
    path can be tested independently of `OnvifRtspFrameSource`.

    Never logs `rtsp_url`: it may embed camera credentials
    (`rtsp://user:pass@host/...`), and TD-15/AGENTS.md forbid that appearing
    in logs or exception messages.
    """

    def __init__(
        self,
        rtsp_url: str,
        source_id: str,
        *,
        open_timeout_ms: int = 5000,
        read_timeout_ms: int = 5000,
        rtsp_transport: str = "tcp",
    ) -> None:
        self._rtsp_url = rtsp_url
        self._source_id = source_id
        self._open_timeout_ms = open_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._rtsp_transport = rtsp_transport
        self._cap: cv2.VideoCapture | None = None

    @property
    def source_id(self) -> str:
        return self._source_id

    async def start(self) -> None:
        cap = await asyncio.to_thread(
            _open_capture,
            self._rtsp_url,
            self._open_timeout_ms,
            self._read_timeout_ms,
            self._rtsp_transport,
        )
        if not cap.isOpened():
            cap.release()
            raise FrameSourceUnavailableError(
                f"Could not open RTSP stream for source {self._source_id!r}"
            )
        self._cap = cap

    async def stop(self) -> None:
        if self._cap is not None:
            await asyncio.to_thread(self._cap.release)
            self._cap = None

    async def frames(self) -> AsyncIterator[Frame]:
        if self._cap is None:
            raise FrameSourceUnavailableError("start() must succeed before frames() is iterated")
        async for frame in _frames_from_capture(self._cap, self._source_id):
            yield frame


class OnvifRtspFrameSource(IFrameSource):
    """Resolves an RTSP URI via ONVIF `GetStreamUri`, then decodes it like `RawRtspFrameSource`.

    ONVIF is only ever a configuration/control plane here — it never touches
    pixels (docs/ARCHITECTURE.md §5). The URI is re-resolved on every
    `start()` (i.e. every reconnect attempt, not just the first connection),
    deliberately: it's a cheap control-plane call, and re-resolving tolerates
    a camera that changed its RTSP URL (e.g. after a reboot) without this
    source getting stuck retrying a stale one.

    Builds its own short-lived `ICameraGateway` per `start()` via
    `camera_gateway_factory` rather than receiving a live gateway instance,
    because this class's constructor args must stay picklable to cross the
    `multiprocessing` "spawn" boundary `StreamWorker` uses (plain str/int
    values only — see `infrastructure/streaming/stream_worker.py`).

    `camera_gateway_factory` has no default and is typed against the
    `ICameraGateway` port only, never a concrete class imported here — the
    composition root (`core/container.py`, the one module allowed to see
    every layer) is what supplies the concrete `OnvifCameraGateway`, so this
    module never imports `infrastructure/onvif/` directly (docs/FOLDER_STRUCTURE.md:
    infrastructure subfolders only talk to each other through ports).
    """

    def __init__(
        self,
        ip_address: str,
        username: str,
        password: str,
        profile_id: str,
        source_id: str,
        camera_gateway_factory: Callable[[], ICameraGateway],
        *,
        port: int = 80,
        rtsp_url_override: str | None = None,
        open_timeout_ms: int = 5000,
        read_timeout_ms: int = 5000,
        rtsp_transport: str = "tcp",
    ) -> None:
        self._ip_address = ip_address
        self._username = username
        self._password = password
        self._port = port
        self._rtsp_url_override = rtsp_url_override
        self._profile_id = profile_id
        self._source_id = source_id
        self._open_timeout_ms = open_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._rtsp_transport = rtsp_transport
        self._camera_gateway_factory = camera_gateway_factory
        self._cap: cv2.VideoCapture | None = None

    @property
    def source_id(self) -> str:
        return self._source_id

    async def start(self) -> None:
        uri = await self._resolve_stream_uri()
        cap = await asyncio.to_thread(
            _open_capture,
            uri,
            self._open_timeout_ms,
            self._read_timeout_ms,
            self._rtsp_transport,
        )
        if not cap.isOpened():
            cap.release()
            raise FrameSourceUnavailableError(
                f"Could not open RTSP stream for source {self._source_id!r}"
            )
        self._cap = cap

    async def _resolve_stream_uri(self) -> str:
        if self._rtsp_url_override is not None:
            return _add_rtsp_credentials(
                self._rtsp_url_override, self._username, self._password
            )
        gateway = self._camera_gateway_factory()
        try:
            await gateway.connect(self._ip_address, self._username, self._password, self._port)
            return await gateway.get_stream_uri(self._profile_id)
        except DomainError:
            raise
        except Exception as exc:
            raise FrameSourceUnavailableError(
                f"Could not resolve a stream URI for source {self._source_id!r}"
            ) from exc
        finally:
            await gateway.disconnect()

    async def stop(self) -> None:
        if self._cap is not None:
            await asyncio.to_thread(self._cap.release)
            self._cap = None

    async def frames(self) -> AsyncIterator[Frame]:
        if self._cap is None:
            raise FrameSourceUnavailableError("start() must succeed before frames() is iterated")
        async for frame in _frames_from_capture(self._cap, self._source_id):
            yield frame
