from typing import override

from pydantic_ai import RunContext

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration


class SocialMediaAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        return f"""
        You are a social media expert. Your task is to turn text into social media text.
        Use emojis and hashtags if appropriate for the platform.
        The text should be in the same language as the input text.
        Turn the following text into a text for social media for {ctx.deps.options}:
        """
