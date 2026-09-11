"""The single Celery task that drives a job end-to-end:

    extract (per content type) -> analyze -> research -> summarize -> save

Every stage transition is written to the `jobs` row so the API (and thus
the frontend, via polling) can show live progress.
"""
from __future__ import annotations

from app.agents.crew import run_summary_crew
from app.core.celery_app import celery_app
from app.db.base import session_scope
from app.db.models import ContentType, Job, JobStatus
from app.ingestion.base import get_extractor
from app.logging_config import get_logger
from app.tasks.errors import GENERIC_ERROR_MESSAGE, friendly_message

logger = get_logger(__name__)


def _set_status(job_id: str, status: JobStatus, stage_message: str) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = status
        job.stage_message = stage_message


def _fail(job_id: str, message: str) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.FAILED
        job.error_message = message
        job.stage_message = "Failed"


@celery_app.task(name="tasks.process_content", bind=True, max_retries=0)
def process_content_job(self, job_id: str) -> None:
    log = logger.bind(job_id=job_id)

    with session_scope() as db:
        job = db.get(Job, job_id)
        if job is None:
            log.error("job_not_found")
            return
        content_type = job.content_type
        title = job.source_reference

    try:
        _set_status(job_id, JobStatus.EXTRACTING, "Extracting content...")
        with session_scope() as db:
            job = db.get(Job, job_id)
            extractor = get_extractor(content_type)
            extracted = extractor.extract(job)

        _set_status(job_id, JobStatus.ANALYZING, "Analyzing content...")

        def on_stage(message: str) -> None:
            stage = JobStatus.RESEARCHING if "esearch" in message else JobStatus.SUMMARIZING
            _set_status(job_id, stage, message)

        summary = run_summary_crew(
            content_type=content_type.value,
            title=extracted.title or title,
            source=title,
            text=extracted.text,
            on_stage=on_stage,
        )

        with session_scope() as db:
            job = db.get(Job, job_id)
            result_payload = summary.model_dump()
            result_payload["content_title"] = extracted.title or title
            result_payload["raw_transcript"] = extracted.raw_transcript
            job.result = result_payload
            job.status = JobStatus.COMPLETED
            job.stage_message = "Done"

        log.info("job_completed")

    except Exception as exc:  # noqa: BLE001 -- intentional catch-all boundary
        message = friendly_message(exc)
        log.error(
            "job_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=exc if message == GENERIC_ERROR_MESSAGE else None,
        )
        _fail(job_id, message)
