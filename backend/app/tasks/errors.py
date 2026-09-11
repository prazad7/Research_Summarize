"""Maps any exception raised during processing to a plain-language message
safe to show the end user. Unrecognized exceptions fall back to a generic
message -- the technical detail always goes to the logs, never to the UI.
"""
from __future__ import annotations

from app.ingestion.exceptions import IngestionError

GENERIC_ERROR_MESSAGE = (
    "Something went wrong while processing your content. Please try again, and if the "
    "problem continues, try a different file or link."
)


def friendly_message(exc: Exception) -> str:
    if isinstance(exc, IngestionError):
        return exc.user_message
    return GENERIC_ERROR_MESSAGE
