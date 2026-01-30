"""Bullet point agent for converting text to bullet points."""

from typing import override

from pydantic_ai import RunContext

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration


class BulletPointAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]):
        return """
            You are an assistant that converts text into a well-structured bullet point format.
            Extract and highlight key points from text.

            Convert to following text into a structured bullet point format.
            Identify and organize main ideas and supporting points.
            The bullet points should be in the same language as the input text.
            Use markdown formatting for bullet points.
            """
