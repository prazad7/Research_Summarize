"""Centralized application configuration.

All runtime configuration is read from environment variables (via a `.env`
file in local/dev, or real environment variables in Docker/VPS). Nothing is
hardcoded so the same image can run on localhost today and on a VPS later
with no code changes -- only environment differences.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App identity / networking -----------------------------------
    APP_NAME: str = "Research & Summarize"
    ENVIRONMENT: str = "local"  # local | staging | production
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Auth -----------------------------------------------------------
    # Shared API key required in the `X-API-Key` header. Leave blank to
    # disable auth entirely (fine for pure localhost experimentation, NOT
    # recommended once the app is reachable from the internet).
    APP_API_KEY: str = ""

    # --- LLM / research providers ---------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    SERPER_API_KEY: str = ""

    # --- Database ---------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/research_summarize"

    # --- Celery / broker --------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # --- File handling ------------------------------------------------------
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 100
    MAX_MEDIA_DURATION_MINUTES: int = 60

    # --- Ingestion behavior --------------------------------------------------
    ENABLE_OCR_FALLBACK: bool = True
    ENABLE_YOUTUBE_AUDIO_FALLBACK: bool = True
    TRUNCATE_CONTENT_CHARS: int = 14000  # keeps LLM context/cost bounded

    # --- Logging ----------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def upload_dir_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
