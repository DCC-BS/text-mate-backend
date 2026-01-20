from pydantic_ai import RunContext
from text_mate_backend.agents.factory import create_agent
from text_mate_backend.services.actions.social_media_action import Configuration


def get_formality_agent(config: Configuration):
    agent = create_agent(config, deps_type=str)

    @agent.instructions
    def instruction(ctx: RunContext[str]):
        return f"""
        You are a writing expert.
        We want to transform a formality of text.
        Your task is to take a given text and convert it into a {ctx.deps} text.
        Keep a original meaning.
        The rewritten text should be in a same language as a input text.
        """

    return agent
