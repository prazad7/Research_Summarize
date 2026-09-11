"""SQLAlchemy engine/session setup.

Kept synchronous on purpose: Celery workers are sync, and FastAPI happily
runs sync DB calls in its threadpool for a job-tracking table with this
access pattern -- no need for the added complexity of an async ORM stack
here. If throughput ever demands it, this module is the only place that
would need to change.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables if they don't exist yet.

    Simple `create_all()` is used instead of Alembic migrations to keep the
    operational footprint small for a first deployment. The schema here is
    a single, stable job-tracking table; if it grows more complex later,
    introducing Alembic is a clean, isolated addition.
    """
    from app.db import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context-managed session for use outside FastAPI (Celery tasks)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
