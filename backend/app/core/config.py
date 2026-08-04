from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# One .env at the repo root serves the whole project (TD-13); resolved by
# path rather than cwd so `uvicorn app.main:app` works the same whether it's
# launched from the repo root or from backend/.
_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


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


settings = Settings()  # type: ignore[call-arg]
