"""Structured outputs the crew's tasks are constrained to produce.

Using `output_pydantic` on each CrewAI Task (instead of hoping the LLM
returns clean JSON) is what lets the API and frontend treat the result as a
typed object instead of parsing free-form text.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ContentAnalysis(BaseModel):
    """Output of the Content Analyst agent -- the first pass over the raw
    extracted text, before any external research is done."""

    draft_headline: str = Field(description="A single-sentence headline capturing the core point")
    candidate_takeaways: list[str] = Field(
        description="4-8 candidate key points from the content, to be refined later"
    )
    entities_and_topics: list[str] = Field(
        description="Notable people, organizations, products, or topics mentioned"
    )
    claims_to_verify: list[str] = Field(
        default_factory=list,
        description="Specific factual claims or topics worth independently verifying or "
        "adding context to via web research",
    )


class SourceItem(BaseModel):
    title: str = Field(description="Title or short label of the source")
    url: str | None = Field(default=None, description="URL of the source, if available")
    note: str = Field(
        description="Plain-language note on what this source confirms/adds, or why a "
        "claim could not be verified"
    )


class ResearchFindings(BaseModel):
    """Output of the Research Verifier agent."""

    sources: list[SourceItem] = Field(default_factory=list)
    verification_summary: str = Field(
        description="Plain-language summary of what was verified, and a note on anything "
        "that could not be confirmed"
    )


class SummaryResult(BaseModel):
    """Final, user-facing output of the crew -- exactly what the frontend renders."""

    headline: str
    key_takeaways: list[str] = Field(description="4-6 clear, plain-language key takeaways")
    entities: list[str] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    verification_notes: str | None = Field(
        default=None,
        description="Plain-language note if something in the content could not be verified",
    )
