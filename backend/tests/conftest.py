"""Test setup.

Environment variables are set BEFORE any `app.*` module is imported, since
`app.config.settings` is instantiated once at import time. Tests run
against a throwaway SQLite file instead of Postgres so they need no
external services -- Celery task execution is mocked out per-test rather
than made eager, since the pipeline calls real external APIs (OpenAI,
Serper, network fetches) that unit tests must not depend on.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_research_summarize.db")
os.environ.setdefault("APP_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SERPER_API_KEY", "test-key")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("UPLOAD_DIR", "./test_uploads")

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base, engine, init_db


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()  # release the sqlite file handle before deleting it (required on Windows)
    db_file = "test_research_summarize.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except PermissionError:
            pass  # best-effort cleanup; a lingering handle shouldn't fail the test run


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)
