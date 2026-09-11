"""Celery application instance.

Broker/backend is Valkey (a fully open-source, Redis-protocol-compatible
in-memory store) -- see docker-compose.yml. Any Redis-protocol URL works
here, so swapping to managed Redis on a cloud provider later is a one-line
env var change.
"""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "research_summarize",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Long-running media jobs: don't let the broker consider a worker dead
    # mid-transcription, and don't prefetch more than one job per worker
    # process so a long job doesn't starve others.
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 1200},
    # Bounds worst-case job runtime even if a dependency misbehaves (e.g. an
    # LLM/tool call that hangs instead of raising). At MAX_MEDIA_DURATION_MINUTES
    # defaults, real transcription + summarization comfortably finishes in a
    # few minutes -- these are a generous but finite ceiling, not a target.
    # SoftTimeLimitExceeded is caught by the task's own exception handler
    # (app/tasks/pipeline.py), so a job that hits it still fails the job
    # cleanly with a friendly message instead of leaving it stuck forever.
    task_time_limit=780,
    task_soft_time_limit=720,
)
