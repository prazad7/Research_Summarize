from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _new_id() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    RESEARCHING = "researching"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"


class ContentType(str, enum.Enum):
    WEBSITE = "website"
    YOUTUBE = "youtube"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    AUDIO = "audio"
    VIDEO = "video"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.PENDING, nullable=False
    )
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, native_enum=False), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "url" | "file"
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)  # URL or original filename
    stored_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    stage_message: Mapped[str] = mapped_column(Text, default="Queued...")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
