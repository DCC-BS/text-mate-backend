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
        Du bist ein Social-Media-Experte. Deine Aufgabe ist es, Text in einen Social-Media-Beitrag umzuwandeln.
        Verwende Emojis und Hashtags, wenn sie zur Plattform passen.
        Wandle den folgenden Text in einen Social-Media-Beitrag für folgende Plattform um: {ctx.deps.options}.
        """
