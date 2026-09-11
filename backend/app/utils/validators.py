from __future__ import annotations

from fastapi import UploadFile

from app.config import settings
from app.ingestion.exceptions import FileTooLargeError


def validate_upload_size(upload: UploadFile) -> None:
    """Checks Content-Length up front; the actual byte count is enforced
    again while streaming to disk in `save_upload`-adjacent callers to
    guard against a missing/incorrect header."""
    size = getattr(upload, "size", None)
    if size is not None and size > settings.max_file_size_bytes:
        raise FileTooLargeError(
            f"That file is larger than the {settings.MAX_FILE_SIZE_MB}MB upload limit."
        )
