"""Custom agent for user-defined prompts."""

from pydantic_ai import Agent, RunContext

from text_mate_backend.agents.factory import create_agent
from text_mate_backend.utils.configuration import Configuration


def get_custom_agent(config: Configuration):
    agent = create_agent(config, deps_type=str, output_type=str)

    @agent.instructions
    def get_intruction(ctx: RunContext[str]):
        return f"""
        You are a writing assistant. Your task is to take a given prompt and rewrite text based on prompt.
        The rewritten text should be in a same language as a input text.
        {ctx.deps}
        """

    return agent
