"""Custom agent for user-defined prompts."""

from typing import override
from pydantic_ai import Agent, RunContext

from pydantic_ai.models import Model
from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.agents.base import BaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration

class CustomAgent(QuickActionBaseAgent):

    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        return f"""
            You are a writing assistant. Your task is to take a given prompt
            and rewrite text based on prompt.
            The rewritten text should be in a same language as a input text.
            {ctx.deps.options}
            """
