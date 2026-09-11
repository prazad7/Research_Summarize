"""Agent role/goal/backstory definitions.

Three agents, each with a narrow job, chained sequentially:
  1. Content Analyst   -- reads the extracted text, drafts the analysis
  2. Research Verifier -- searches the web to verify/contextualize claims
  3. Summary Writer     -- synthesizes everything into the final user-facing result
"""
from __future__ import annotations

from crewai import Agent

from app.agents.llm import get_llm
from app.agents.tools import get_search_tool


def build_content_analyst() -> Agent:
    return Agent(
        role="Content Analyst",
        goal=(
            "Read the extracted content carefully and identify its core message, the most "
            "important points, notable entities/topics, and any specific factual claims that "
            "are worth independently verifying."
        ),
        backstory=(
            "You are a meticulous analyst who has read thousands of articles, transcripts, "
            "and documents. You are excellent at separating the signal from the noise and "
            "flagging claims that deserve a second look rather than being taken at face value."
        ),
        llm=get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=5,  # these are single-pass tasks; bounds retry/tool-loop time if the LLM misbehaves
    )


def build_research_verifier() -> Agent:
    return Agent(
        role="Research Verifier",
        goal=(
            "Use web search to verify or add credible context to the claims and topics "
            "flagged by the Content Analyst. For each one, find a real, citable source. If "
            "something cannot be verified, say so plainly instead of guessing."
        ),
        backstory=(
            "You are a careful fact-checker and research assistant. You never fabricate "
            "sources or URLs -- you only cite what your search tool actually returns, and "
            "you are comfortable reporting 'could not be verified' when that's the truth."
        ),
        tools=[get_search_tool()],
        llm=get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=5,  # these are single-pass tasks; bounds retry/tool-loop time if the LLM misbehaves
    )


def build_summary_writer() -> Agent:
    return Agent(
        role="Summary Writer",
        goal=(
            "Synthesize the content analysis and research findings into a single, clear, "
            "well-organized summary that a non-technical reader can understand in under a "
            "minute."
        ),
        backstory=(
            "You are a skilled editor who writes for busy, non-technical readers. You favor "
            "plain language over jargon, keep takeaways concrete and specific, and never "
            "invent facts or sources that weren't provided to you."
        ),
        llm=get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=5,  # these are single-pass tasks; bounds retry/tool-loop time if the LLM misbehaves
    )
