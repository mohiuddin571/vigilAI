import asyncio
import contextlib
from pathlib import Path

import structlog

from app.application.ports.rtmp_server_controller import IRtmpServerController
from app.domain.exceptions import RtmpServerUnavailableError
from app.domain.value_objects.rtmp_server_status import RtmpServerStatus

logger = structlog.get_logger(__name__)

_STARTUP_GRACE_SECONDS = 0.3
_TERMINATE_TIMEOUT_SECONDS = 5.0
_KILL_TIMEOUT_SECONDS = 3.0


class MediaMtxServerController(IRtmpServerController):
    """`IRtmpServerController` implementation: a MediaMTX subprocess restricted to RTMP only.

    docs/TECHNICAL_DECISIONS.md TD-33: MediaMTX is the smallest component
    that actually provides "publish independently of consume" over RTMP —
    nothing else in this codebase does. Spawned/reaped the same way
    `FfmpegRecordingWorker` (TD-22) owns its ffmpeg subprocess: plain
    `asyncio.create_subprocess_exec`, terminate-then-kill on `stop()`, never
    Python `multiprocessing` — there's no Python decode loop to isolate here,
    MediaMTX itself is already the isolated OS process doing the work.

    Renders its own minimal YAML config on every `start()` rather than
    shipping a static file, so every RTMP-relevant value
    (host/port/publish+read auth) stays driven by `Settings` alone, per
    AGENTS.md "config only via the single `Settings` object" — hand-written
    rather than via a YAML library: this is one flat, fully-controlled
    document, and a new dependency isn't warranted just for it.

    Never logs the rendered config or any credential value (TD-15).
    """

    def __init__(
        self,
        binary_path: str,
        runtime_dir: Path,
        *,
        host: str,
        port: int,
        app_name: str,
        stream_key: str,
        publish_username: str | None,
        publish_password: str | None,
        read_username: str | None,
        read_password: str | None,
    ) -> None:
        self._binary_path = binary_path
        self._runtime_dir = runtime_dir
        self._host = host
        self._port = port
        self._app_name = app_name
        self._stream_key = stream_key
        self._publish_username = publish_username
        self._publish_password = publish_password
        self._read_username = read_username
        self._read_password = read_password
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        if self._process is not None and self._process.returncode is None:
            return

        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        config_path = self._runtime_dir / "mediamtx.yml"
        config_path.write_text(self._render_config())

        try:
            process = await asyncio.create_subprocess_exec(
                self._binary_path,
                str(config_path),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise RtmpServerUnavailableError(
                "Could not start the RTMP demo server (mediamtx) — is it installed "
                "and on PATH? See docs/RTMP_DEMO.md."
            ) from exc

        # An unparsable config or a port already in use makes mediamtx exit
        # almost immediately rather than hang — a short grace window turns
        # that into a raised error instead of `status()` falsely reporting
        # "running" right after `start()` returns.
        await asyncio.sleep(_STARTUP_GRACE_SECONDS)
        if process.returncode is not None:
            raise RtmpServerUnavailableError(
                f"mediamtx exited immediately (code {process.returncode}) — "
                f"port {self._port} may already be in use."
            )

        self._process = process
        logger.info("rtmp_demo.server_started", pid=process.pid, port=self._port)

    async def stop(self) -> None:
        process = self._process
        if process is None:
            return
        self._process = None
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_TIMEOUT_SECONDS)
            except TimeoutError:
                logger.warning("rtmp_demo.server_force_kill", pid=process.pid)
                process.kill()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=_KILL_TIMEOUT_SECONDS)
        logger.info("rtmp_demo.server_stopped", pid=process.pid, returncode=process.returncode)

    def status(self) -> RtmpServerStatus:
        process = self._process
        running = process is not None and process.returncode is None
        return RtmpServerStatus(
            running=running,
            pid=process.pid if running and process is not None else None,
            host=self._host,
            port=self._port,
            app_name=self._app_name,
            stream_key=self._stream_key,
        )

    def _render_config(self) -> str:
        lines = [
            "logLevel: info",
            "logDestinations: [stdout]",
            "api: false",
            "metrics: false",
            "pprof: false",
            "playback: false",
            "rtsp: no",
            "rtmp: yes",
            f"rtmpAddress: :{self._port}",
            "hls: no",
            "webrtc: no",
            "srt: no",
            # MediaMTX 1.20+ also starts a MoQ listener by default, on fixed
            # ports (8892/8893) that aren't derived from `rtmpAddress` above
            # — left enabled, two RTMP demo instances (or a leftover
            # `mediamtx` from a previous run) would fail to start with an
            # unrelated "address already in use" even though the RTMP port
            # itself was free. This demo only ever needs RTMP.
            "moq: no",
            "paths:",
            "  all_others:",
            "authInternalUsers:",
            *self._auth_users_yaml(),
        ]
        return "\n".join(lines) + "\n"

    def _auth_users_yaml(self) -> list[str]:
        """Build MediaMTX's `authInternalUsers` list (checked on both PUBLISH and PLAY).

        One entry per configured named user, each restricted to just that
        action — this is the RTMP auth demo's entire mechanism
        (docs/RTMP_DEMO.md). MediaMTX denies every action by default once any
        named user is configured, so a trailing `any` user grants back
        whichever of publish/read was left without credentials, keeping
        partial auth config from accidentally locking out the other side.
        """
        lines: list[str] = []
        open_actions: list[str] = []

        if self._publish_username and self._publish_password:
            lines += self._user_entry(self._publish_username, self._publish_password, "publish")
        else:
            open_actions.append("publish")

        if self._read_username and self._read_password:
            lines += self._user_entry(self._read_username, self._read_password, "read")
        else:
            open_actions.append("read")

        if open_actions:
            lines += self._user_entry("any", None, *open_actions)

        return lines

    @staticmethod
    def _user_entry(user: str, password: str | None, *actions: str) -> list[str]:
        lines = [
            f"  - user: {_yaml_str(user)}",
            f"    pass: {_yaml_str(password) if password is not None else ''}",
            "    permissions:",
        ]
        lines += [f"      - action: {action}" for action in actions]
        return lines


def _yaml_str(value: str) -> str:
    """Double-quote a scalar for the hand-written YAML above, escaping embedded quotes/backslashes
    so an operator-supplied username/password can't break the document's structure."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
