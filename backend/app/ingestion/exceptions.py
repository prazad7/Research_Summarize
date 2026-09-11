"""Ingestion-layer exceptions.

Every exception here carries a `user_message`: plain language, safe to show
directly in the UI, with no stack traces or internal details. The original
technical exception (if any) is preserved via `__cause__` / `original` for
structured logging only.
"""
from __future__ import annotations


class IngestionError(Exception):
    """Base class for all content-extraction failures."""

    default_message = "We couldn't process that content. Please try again."

    def __init__(self, user_message: str | None = None, *, original: Exception | None = None):
        self.user_message = user_message or self.default_message
        self.original = original
        super().__init__(self.user_message)


class UnsupportedContentError(IngestionError):
    default_message = (
        "That type of content isn't supported yet. Try a website link, YouTube link, "
        "PDF, Word, Excel, PowerPoint, audio, or video file."
    )


class FileTooLargeError(IngestionError):
    default_message = "That file is larger than the current upload limit."


class MediaTooLongError(IngestionError):
    default_message = "That recording is longer than the current duration limit."


class UnreachableSourceError(IngestionError):
    default_message = "We couldn't reach that link. Please check the URL and try again."


class CorruptFileError(IngestionError):
    default_message = (
        "That file appears to be damaged or in an unexpected format and couldn't be opened."
    )


class NoExtractableTextError(IngestionError):
    default_message = (
        "We couldn't find any readable text in that file. If it's a scanned document, "
        "it may need OCR support, or the pages may be image-only."
    )


class NoTranscriptAvailableError(IngestionError):
    default_message = (
        "No transcript or captions are available for that video, and automatic "
        "transcription wasn't able to produce one either."
    )


class TranscriptionError(IngestionError):
    default_message = "We couldn't transcribe that audio or video recording."
