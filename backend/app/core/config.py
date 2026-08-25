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

    # Recording (M6, T-060; docs/TECHNICAL_DECISIONS.md TD-22). Segment
    # duration is a production-reasonable default, not fixed by any planning
    # doc; storage path mirrors FOLDER_STRUCTURE.md's `storage/recordings/`.
    recording_output_dir: Path = _REPO_ROOT / "storage" / "recordings"
    recording_segment_duration_seconds: int = 300
    ffmpeg_binary_path: str = "ffmpeg"
    ffprobe_binary_path: str = "ffprobe"

    # YOLO object detection/classification (M9, T-090/T-091;
    # docs/TECHNICAL_DECISIONS.md TD-25). `yolo_model_path` is a full path
    # (not just a filename) under the gitignored storage/models/ so
    # Ultralytics' own download-if-missing behavior writes weights exactly
    # there — that's the entire caching mechanism, no separate download
    # script needed (T-090's "cached thereafter"). Confidence/IoU thresholds
    # match Ultralytics' own upstream defaults, made explicit here per TD-13.
    yolo_model_path: Path = _REPO_ROOT / "storage" / "models" / "yolov8n.pt"
    yolo_confidence_threshold: float = 0.25
    yolo_iou_threshold: float = 0.45
    # None lets Ultralytics auto-select a device (CUDA > Apple MPS > CPU) at
    # inference time rather than this project guessing the deployment box.
    yolo_device: str | None = None

    # License Plate Recognition / OCR (M13, T-131/T-133;
    # docs/TECHNICAL_DECISIONS.md TD-30). `easyocr_model_storage_dir` mirrors
    # `yolo_model_path`'s convention of caching under the gitignored
    # storage/models/ (docs/FOLDER_STRUCTURE.md already names "EasyOCR model
    # cache" as belonging there). `easyocr_gpu` defaults to False: EasyOCR's
    # Apple-Silicon MPS support is inconsistent across versions (unlike
    # Ultralytics' own auto device selection, TD-25), so this defaults to the
    # deterministic CPU path rather than assuming MPS acceleration works.
    easyocr_languages: list[str] = ["en"]
    easyocr_model_storage_dir: Path = _REPO_ROOT / "storage" / "models" / "easyocr"
    easyocr_gpu: bool = False
    # Reads below this confidence are treated as "no text could be read"
    # (ILicensePlateReader's own `None` contract) rather than emitted as a
    # low-quality DetectionEvent.
    easyocr_min_confidence: float = 0.3
    # Bounded, drop-oldest queue between plate localization and the
    # background OCR worker task (T-133) — same pattern as
    # `stream_worker_frame_queue_max_size` (M2, TD-20).
    lpr_ocr_queue_max_size: int = 10

    # Demo video library (M17, T-205). Gitignored, like storage/recordings/
    # and storage/models/ — operators drop their own pre-recorded clips here
    # to demo analytics (e.g. License Plate Recognition) without a live
    # camera. Scanned directly from disk, no DB table (docs/FOLDER_STRUCTURE.md).
    demo_videos_dir: Path = _REPO_ROOT / "storage" / "demo_videos"

    # RTMP Push/Consume Demo (docs/RTMP_DEMO.md; docs/TECHNICAL_DECISIONS.md
    # TD-33). Outside the graded milestone sequence — an isolated demo page
    # proving Video File -> ffmpeg RTMP Publisher -> MediaMTX RTMP Server ->
    # RTMP Consumer -> Player, since there is no physical RTMP camera.
    # `mediamtx_binary_path` mirrors `ffmpeg_binary_path`/`ffprobe_binary_path`
    # above: a configured binary name/path, never resolved via os.environ
    # outside this file.
    mediamtx_binary_path: str = "mediamtx"
    rtmp_server_host: str = "localhost"
    rtmp_server_port: int = 1935
    rtmp_app_name: str = "live"
    rtmp_stream_key: str = "demo-camera"
    # None/empty (either half unset) = auth disabled — the intentionally
    # simplified local-demo default documented in docs/RTMP_DEMO.md. Setting
    # both halves of a pair enables MediaMTX's built-in per-action
    # `authInternalUsers` check for that action.
    rtmp_publish_username: str | None = None
    rtmp_publish_password: str | None = None
    rtmp_read_username: str | None = None
    rtmp_read_password: str | None = None
    # Publisher (ffmpeg) encode target — also what the Consumer UI reports as
    # the stream's "configured" (not independently measured) codec/bitrate,
    # since cv2.VideoCapture's FFmpeg backend doesn't reliably expose true
    # codec/bitrate for a network source (see start_rtmp_consumer.py).
    rtmp_publish_video_bitrate_kbps: int = 2000
    rtmp_publish_resolution: str = "1280x720"
    rtmp_publish_fps: int = 25
    # RTMP consume decode (Consumer side, `RtmpFrameSource`): same open/read-
    # timeout-before-treating-as-a-failed-connection-attempt purpose as
    # rtsp_open_timeout_ms/rtsp_read_timeout_ms above, kept separate since
    # the two sources aren't required to share a value. `rtmp_open_timeout_ms`
    # is higher than the RTSP equivalent to comfortably cover
    # RtmpFrameSource's wider ffmpeg probe window (10s analyzeduration) —
    # see that module's docstring.
    rtmp_open_timeout_ms: int = 12000
    rtmp_read_timeout_ms: int = 5000
    # Generated mediamtx.yml (and nothing else) lives here — gitignored, like
    # storage/recordings/ and storage/demo_videos/ above.
    rtmp_demo_runtime_dir: Path = _REPO_ROOT / "storage" / "rtmp_demo"


settings = Settings()  # type: ignore[call-arg]
