"""Postprocessing utilities for agent outputs."""


def trim_text(text: str) -> str:
    """Remove blank lines from start and end of text."""
    lines = text.split('\n')
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = len(lines) - 1
    while end >= start and not lines[end].strip():
        end -= 1
    return '\n'.join(lines[start:end + 1])
