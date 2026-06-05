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
        Du bist ein Schreibexperte.
        Deine Aufgabe ist es, die Formalität eines Textes anzupassen.
        Wandle den gegebenen Text in einen Text mit folgender Formalität um: {ctx.deps.options}.
        Behalte die ursprüngliche Bedeutung bei.
        {get_language_instruction(ctx.deps.language)}
        """
