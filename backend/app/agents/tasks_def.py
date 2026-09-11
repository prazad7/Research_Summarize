from __future__ import annotations

from typing import Callable

from crewai import Agent, Task

from app.agents.schemas import ContentAnalysis, ResearchFindings, SummaryResult

StageCallback = Callable[[str], None] | None


def build_analysis_task(agent: Agent, content_type: str, title: str, source: str, text: str) -> Task:
    return Task(
        description=(
            f"Analyze the following {content_type} content titled '{title}' (source: {source}).\n\n"
            "Identify: a draft one-sentence headline, 4-8 candidate key takeaways, notable "
            "entities/topics mentioned, and a short list of specific factual claims worth "
            "verifying via web search (skip this list if the content is purely opinion or "
            "narrative with nothing checkable).\n\n"
            f"--- CONTENT START ---\n{text}\n--- CONTENT END ---"
        ),
        expected_output="A structured content analysis.",
        agent=agent,
        output_pydantic=ContentAnalysis,
    )


def build_research_task(agent: Agent, analysis_task: Task) -> Task:
    return Task(
        description=(
            "Using the claims_to_verify and entities_and_topics from the previous analysis, "
            "use web search to verify or add credible context to each one. For every claim or "
            "topic you search for, record a source (title + URL) and a short plain-language "
            "note on what it confirms or adds. If a claim cannot be verified after a "
            "reasonable search attempt, include it with a note explaining that it could not "
            "be verified -- do not fabricate a source. If there is nothing to verify, return "
            "an empty sources list and say so in the verification_summary."
        ),
        expected_output="A structured list of research findings and sources.",
        agent=agent,
        context=[analysis_task],
        output_pydantic=ResearchFindings,
    )


def build_writing_task(
    agent: Agent, analysis_task: Task, research_task: Task, content_type: str, title: str
) -> Task:
    return Task(
        description=(
            f"Using the content analysis and research findings for this {content_type} "
            f"titled '{title}', write the final summary for a non-technical reader:\n"
            "- headline: one clear sentence capturing the core point\n"
            "- key_takeaways: exactly 4-6 concrete, plain-language bullet points\n"
            "- entities: the most notable people/organizations/topics (keep it short, max 8)\n"
            "- sources: carry over the verified sources from the research step, unchanged\n"
            "- verification_notes: a short plain-language note if anything could not be "
            "verified, or null if everything checked out (or nothing needed checking)\n"
            "Do not invent facts, sources, or URLs that weren't provided to you."
        ),
        expected_output="The final structured summary.",
        agent=agent,
        context=[analysis_task, research_task],
        output_pydantic=SummaryResult,
    )
