"""Follow-up chat over a completed job: `/api/jobs/{job_id}/messages`.

Synchronous by design (unlike the main pipeline's job-queue + polling
pattern): a single grounded LLM call normally answers in a few seconds, so
the frontend just awaits the POST response rather than polling -- see the
README's "light, single-user traffic" sizing note. Only available once a
job has a completed summary, since that's what answers are grounded in.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.chat import build_chat_reply
from app.db.base import get_db
from app.db.models import ChatMessage, ChatRole, Job, JobStatus
from app.logging_config import get_logger
from app.schemas.chat import ChatMessageCreate, ChatMessageOut
from app.security import require_api_key

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/jobs/{job_id}/messages",
    tags=["chat"],
    dependencies=[Depends(require_api_key)],
)

# Bounds how many prior turns are replayed into each new prompt -- keeps
# LLM cost/latency bounded for a long-running conversation without cutting
# off history entirely.
_MAX_HISTORY_TURNS = 16


def _get_chat_ready_job(job_id: str, db: Session) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.status != JobStatus.COMPLETED or not job.result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job hasn't finished summarizing yet -- chat is available once it's completed.",
        )
    return job


def _summary_text(result: dict) -> str:
    takeaways = "\n".join(f"- {t}" for t in result.get("key_takeaways", []))
    return f"{result.get('headline', '')}\n\n{takeaways}"


def _ordered_messages(job_id: str, db: Session) -> list[ChatMessage]:
    stmt = select(ChatMessage).where(ChatMessage.job_id == job_id).order_by(ChatMessage.created_at)
    return list(db.scalars(stmt))


@router.get("", response_model=list[ChatMessageOut])
def list_messages(job_id: str, db: Session = Depends(get_db)) -> list[ChatMessage]:
    _get_chat_ready_job(job_id, db)
    return _ordered_messages(job_id, db)


@router.post("", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    job_id: str, payload: ChatMessageCreate, db: Session = Depends(get_db)
) -> ChatMessage:
    job = _get_chat_ready_job(job_id, db)
    user_text = payload.message.strip()

    prior = _ordered_messages(job_id, db)[-_MAX_HISTORY_TURNS:]
    history = [{"role": m.role.value, "content": m.content} for m in prior]

    # Committed before the LLM call (rather than in the same transaction as
    # the reply) so a failed/slow LLM call never loses the user's own
    # message -- it stays in history and they aren't forced to retype it.
    user_msg = ChatMessage(job_id=job_id, role=ChatRole.USER, content=user_text)
    db.add(user_msg)
    db.commit()

    try:
        reply_text = build_chat_reply(
            title=(job.result or {}).get("content_title") or job.source_reference,
            content_type=job.content_type.value,
            extracted_text=job.extracted_text or "(no extracted source text was saved for this job)",
            summary_text=_summary_text(job.result or {}),
            history=history,
            user_message=user_text,
        )
    except Exception:
        logger.error("chat_reply_failed", job_id=job_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't get a reply right now. Please try again.",
        )

    assistant_msg = ChatMessage(job_id=job_id, role=ChatRole.ASSISTANT, content=reply_text)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    logger.info("chat_reply_sent", job_id=job_id)
    return assistant_msg
