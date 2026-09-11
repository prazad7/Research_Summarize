"""The entire public API surface: submit content, poll job status/result.

POST /api/jobs accepts EITHER a `url` form field OR a `file` upload (never
both) and immediately enqueues background processing, returning a job_id
right away -- the client then polls GET /api/jobs/{id} until status is
"completed" or "failed".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import ContentType, Job, JobStatus
from app.ingestion.detect import detect_from_filename, detect_from_url
from app.ingestion.exceptions import IngestionError
from app.logging_config import get_logger
from app.schemas.job import JobCreateResponse, JobStatusResponse
from app.security import require_api_key
from app.storage.file_storage import save_upload
from app.tasks.pipeline import process_content_job
from app.utils.validators import validate_upload_size

logger = get_logger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> JobCreateResponse:
    if bool(url) == bool(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submit exactly one of: a URL, or a file upload.",
        )

    try:
        if url:
            content_type = detect_from_url(url)
            job = Job(
                status=JobStatus.PENDING,
                content_type=content_type,
                source_type="url",
                source_reference=url.strip(),
            )
            db.add(job)
            db.flush()
        else:
            validate_upload_size(file)
            content_type = detect_from_filename(file.filename or "")
            job = Job(
                status=JobStatus.PENDING,
                content_type=content_type,
                source_type="file",
                source_reference=file.filename or "uploaded file",
            )
            db.add(job)
            db.flush()
            stored_path = save_upload(job.id, file)
            job.stored_file_path = str(stored_path)

        db.commit()
        db.refresh(job)

    except IngestionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.user_message)

    process_content_job.delay(job.id)
    logger.info("job_created", job_id=job.id, content_type=content_type.value)

    return JobCreateResponse(job_id=job.id, status=job.status, content_type=job.content_type)


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    # Built explicitly (rather than returned via from_attributes) since the
    # ORM's primary key is `Job.id` while the API's public field is `job_id`.
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        stage_message=job.stage_message,
        content_type=job.content_type,
        source_reference=job.source_reference,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=job.result,
        error_message=job.error_message,
    )
