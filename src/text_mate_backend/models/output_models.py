"""Structured output types for agents."""

from typing import Literal, TypedDict


class SummaryOutput(TypedDict):
    """Structured output for summarization."""
    summary: str
    key_points: list[str]
    original_length: int
    summary_length: int


class RewriteOutput(TypedDict):
    """Structured output for text rewriting."""
    rewritten_text: str
    changes_made: list[str]
    tone: Literal['formal', 'casual', 'neutral']


class GenericOutput(TypedDict):
    """Generic output for any text processing task."""
    result: str
    metadata: dict[str, str]
