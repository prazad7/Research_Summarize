from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.config import settings


def save_upload(job_id: str, upload: UploadFile) -> Path:
    """Streams an uploaded file to disk under a job-scoped, collision-safe name."""
    suffix = Path(upload.filename or "").suffix
    dest = settings.upload_dir_path / f"{job_id}{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    return dest


def delete_file(path: str | None) -> None:
    if not path:
        return
    Path(path).unlink(missing_ok=True)
