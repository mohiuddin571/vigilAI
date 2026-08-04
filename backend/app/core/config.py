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


settings = Settings()  # type: ignore[call-arg]
