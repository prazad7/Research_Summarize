"""Maps a user submission (URL or uploaded filename) to a ContentType.

Adding a new input type later is a two-line change here plus one new
extractor class -- nothing else in the system needs to know about it.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from app.db.models import ContentType
from app.ingestion.exceptions import UnsupportedContentError

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}

_EXTENSION_MAP: dict[str, ContentType] = {
    ".pdf": ContentType.PDF,
    ".doc": ContentType.DOCX,
    ".docx": ContentType.DOCX,
    ".xls": ContentType.XLSX,
    ".xlsx": ContentType.XLSX,
    ".ppt": ContentType.PPTX,
    ".pptx": ContentType.PPTX,
    ".mp3": ContentType.AUDIO,
    ".wav": ContentType.AUDIO,
    ".m4a": ContentType.AUDIO,
    ".aac": ContentType.AUDIO,
    ".ogg": ContentType.AUDIO,
    ".flac": ContentType.AUDIO,
    ".mp4": ContentType.VIDEO,
    ".mov": ContentType.VIDEO,
    ".avi": ContentType.VIDEO,
    ".mkv": ContentType.VIDEO,
    ".webm": ContentType.VIDEO,
}

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def detect_from_url(url: str) -> ContentType:
    if not _URL_RE.match(url.strip()):
        raise UnsupportedContentError("Please enter a valid http:// or https:// link.")

    host = urlparse(url.strip()).netloc.lower()
    if host in _YOUTUBE_HOSTS:
        return ContentType.YOUTUBE
    return ContentType.WEBSITE


def detect_from_filename(filename: str) -> ContentType:
    ext = Path(filename).suffix.lower()
    content_type = _EXTENSION_MAP.get(ext)
    if content_type is None:
        raise UnsupportedContentError(
            f"Files with the \"{ext or 'unknown'}\" extension aren't supported yet."
        )
    return content_type
