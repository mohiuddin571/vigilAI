from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# One .env at the repo root serves the whole project (TD-13); resolved by
# path rather than cwd so `uvicorn app.main:app` works the same whether it's
# launched from the repo root or from backend/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT_ENV_FILE = _REPO_ROOT / ".env"
_DEFAULT_DATABASE_PATH = _REPO_ROOT / "storage" / "db" / "vigilai.db"


class Settings(BaseSettings):
    """The single source of configuration for the whole process tree.

    Every environment variable the application reads must be declared here —
    no module outside this file reads `os.environ` directly (see AGENTS.md
    "Things AI Must Never Do").
    """

    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV_FILE, env_file_encoding="utf-8")

    environment: Literal["development", "staging", "production"]
    log_level: str = "INFO"
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # Required, no default (TD-15): the key must come from environment config,
    # never be baked into source. Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    camera_credential_encryption_key: str

    # SQLite for development (TD-09); overridable for a future Postgres path.
    database_url: str = f"sqlite+aiosqlite:///{_DEFAULT_DATABASE_PATH}"

    # Stream Worker reconnect/backoff (M2, T-024; shared by every IFrameSource,
    # camera or file — docs/ARCHITECTURE.md §6.2). Seconds, applied in order
    # and held at the last value once exhausted (i.e. capped, not exhausted-and-give-up).
    stream_worker_reconnect_backoff_seconds: list[float] = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]

    # Bounded, drop-oldest frame queue size per Stream Worker (M2, T-023).
    stream_worker_frame_queue_max_size: int = 10

    # RTSP decode (M5, T-050/T-051): how long `cv2.VideoCapture`'s FFmpeg
    # backend waits to open/read an RTSP source before treating it as a
    # failed connection attempt (which `ReconnectSupervisor` then retries).
    rtsp_open_timeout_ms: int = 5000
    rtsp_read_timeout_ms: int = 5000
    # Public RTSP port-forwards commonly expose the control TCP port but not
    # the separate UDP RTP ports, so interleaved TCP is the safe default.
    rtsp_transport: Literal["tcp", "udp"] = "tcp"

    # MJPEG live-view (M5, T-052; TD-10).
    mjpeg_boundary: str = "frame"
    mjpeg_jpeg_quality: int = 80

    # WebSocket stream-status channel poll interval (M5, T-053).
    stream_status_poll_interval_seconds: float = 1.0


settings = Settings()  # type: ignore[call-arg]
