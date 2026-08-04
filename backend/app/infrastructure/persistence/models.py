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
