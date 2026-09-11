"""Assembles and runs the summarization crew.

Sequential process, three chained tasks:
    Content Analyst -> Research Verifier -> Summary Writer

`on_stage` is called as each task completes so the caller (the Celery task)
can move the job's visible status forward (e.g. "Researching...",
"Summarizing...") without the crew needing to know anything about jobs,
Celery, or the database.
"""
from __future__ import annotations

from typing import Callable

from crewai import Crew, Process, TaskOutput

from app.agents.agents_def import build_content_analyst, build_research_verifier, build_summary_writer
from app.agents.schemas import SummaryResult
from app.agents.tasks_def import build_analysis_task, build_research_task, build_writing_task
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

OnStage = Callable[[str], None]


def run_summary_crew(
    *,
    content_type: str,
    title: str,
    source: str,
    text: str,
    on_stage: OnStage | None = None,
) -> SummaryResult:
    truncated = text[: settings.TRUNCATE_CONTENT_CHARS]
    was_truncated = len(text) > settings.TRUNCATE_CONTENT_CHARS

    analyst = build_content_analyst()
    verifier = build_research_verifier()
    writer = build_summary_writer()

    analysis_task = build_analysis_task(analyst, content_type, title, source, truncated)
    research_task = build_research_task(verifier, analysis_task)
    writing_task = build_writing_task(writer, analysis_task, research_task, content_type, title)

    def _on_analysis_done(output: TaskOutput) -> None:
        if on_stage:
            on_stage("Researching and verifying key points...")

    def _on_research_done(output: TaskOutput) -> None:
        if on_stage:
            on_stage("Writing the final summary...")

    analysis_task.callback = _on_analysis_done
    research_task.callback = _on_research_done

    crew = Crew(
        agents=[analyst, verifier, writer],
        tasks=[analysis_task, research_task, writing_task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    summary: SummaryResult = result.pydantic  # writing_task's output_pydantic

    if was_truncated and not summary.verification_notes:
        summary.verification_notes = (
            "This content was long, so the summary is based on the first "
            f"{settings.TRUNCATE_CONTENT_CHARS:,} characters extracted."
        )

    return summary
