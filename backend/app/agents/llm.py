"""Single place that constructs the LLM used by every agent.

Swapping providers/models later (e.g. a different OpenAI model, or a
different provider entirely) means changing this one function -- no agent
definition anywhere else references a model name directly.
"""
from __future__ import annotations

from crewai import LLM

from app.config import settings


def get_llm(*, temperature: float = 0.3) -> LLM:
    return LLM(
        model=f"openai/{settings.OPENAI_MODEL}",
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
        timeout=60,  # bounds a single stalled call; Celery's task time limit bounds the whole job
    )
