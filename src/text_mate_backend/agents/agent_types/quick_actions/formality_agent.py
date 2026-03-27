from typing import override

from pydantic_ai import RunContext

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.agents.agent_utils import get_language_instruction
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration


class FormalityAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        return f"""
        You are a writing expert.
        We want to transform the formality of the text.
        Your task is to take a given text and convert it into a {ctx.deps.options} text.
        Keep a original meaning.
        {get_language_instruction(ctx.deps.language)}
        """
