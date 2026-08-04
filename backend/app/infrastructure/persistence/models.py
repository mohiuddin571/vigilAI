from datetime import datetime

from sqlmodel import Field, SQLModel


class CameraRow(SQLModel, table=True):
    """SQL row shape for an onboarded camera (TD-09).

    `encrypted_password` is Fernet ciphertext (see `security/credential_cipher.py`)
    — never plaintext. `stream_profiles_json` is a JSON-encoded list of profile
    dicts; this milestone has no need to query profiles independently of their
    camera, so a normalized child table would be speculative.
    """

    __tablename__ = "camera"

    id: str = Field(primary_key=True)
    name: str
    ip_address: str
    port: int
    username: str
    encrypted_password: str
    rtsp_url_override: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    is_online: bool = False
    stream_profiles_json: str = "[]"


class RecordingRow(SQLModel, table=True):
    """SQL row shape for one recorded segment file (TD-09, M6/TD-22).

    One row per physical segment file produced by the Recording Worker's
    ffmpeg segment muxer — `Recording` itself was not extended to hold
    multiple file paths (see TECHNICAL_DECISIONS.md TD-22).
    """

    __tablename__ = "recording"

    id: str = Field(primary_key=True)
    camera_id: str = Field(index=True)
    file_path: str
    started_at: datetime
    ended_at: datetime | None = None
    size_bytes: int | None = None


class DetectionEventRow(SQLModel, table=True):
    """SQL row shape for one analytics finding (TD-09, M8/TD-24).

    `bounding_box_json`/`metadata_json` are JSON-encoded (mirrors
    `CameraRow.stream_profiles_json`) — `DetectionEvent.metadata` is an
    open-ended `dict[str, Any]` bag by design (M1), so a normalized column
    set would be speculative ahead of M9+'s real detector plugins.
    """

    __tablename__ = "detection_event"

    id: str = Field(primary_key=True)
    camera_id: str = Field(index=True)
    event_type: str = Field(index=True)
    occurred_at: datetime
    confidence: float
    bounding_box_json: str | None = None
    metadata_json: str = "{}"
