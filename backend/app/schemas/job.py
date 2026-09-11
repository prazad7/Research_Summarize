from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.agents.schemas import SummaryResult
from app.db.models import ContentType, JobStatus


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    content_type: ContentType


class JobResultPayload(SummaryResult):
    content_title: str | None = None
    raw_transcript: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    stage_message: str
    content_type: ContentType
    source_reference: str
    created_at: datetime
    updated_at: datetime
    result: JobResultPayload | None = None
    error_message: str | None = None
