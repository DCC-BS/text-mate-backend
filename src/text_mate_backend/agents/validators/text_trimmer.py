"""Text trimming validator for agent outputs."""

from pydantic_ai import Agent, RunContext
from typing import TypeVar, Any

from text_mate_backend.agents.postprocessing import trim_text

T = TypeVar('T')


def apply_text_trimmer[T](agent: Agent[Any, T]) -> Agent[Any, T]:
    """Apply text trimming to agent string outputs."""

    @agent.output_validator
    def trim_validator(ctx: RunContext, output: T) -> T:
        if isinstance(output, str):
            return trim_text(output)  # type: ignore
        return output

    return agent
