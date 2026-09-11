"""Tool wiring for the crew.

SerperDevTool (crewai_tools) wraps the Serper.dev Google Search API -- an
affordable, widely-used open API for giving agents real web-search
capability. It reads SERPER_API_KEY from the environment automatically.
"""
from __future__ import annotations

from crewai_tools import SerperDevTool


def get_search_tool() -> SerperDevTool:
    return SerperDevTool(n_results=5)
