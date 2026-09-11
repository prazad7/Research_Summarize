"""Simple shared-secret API key gate.

Intended for a single-user / small-team deployment on a public VPS -- not a
full auth system. If APP_API_KEY is left blank (pure local dev), the check
is skipped entirely. Swapping this for real user accounts later only means
replacing this one dependency; nothing else in the app depends on it.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.APP_API_KEY:
        return  # auth disabled (local/dev default)

    if x_api_key != settings.APP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )
