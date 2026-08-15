from typing import override

from pydantic_ai import RunContext

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration


class FormalityAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @property
    def agent_name(self) -> str:
        return "Formality Agent"

    @property
    def agent_description(self) -> str:
        return "Adjusts the formality level of a text while preserving its meaning"

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        formality_de = (
            "formell"
            if ctx.deps.options == "formal"
            else "informell"
            if ctx.deps.options == "informal"
            else ctx.deps.options
        )
        return f"""
        Du bist ein Schreibexperte.
        Deine Aufgabe ist es, das Formalitätsniveau eines Textes anzupassen.
        Wandle den gegebenen Text in einen Text mit folgendem Formalitätsniveau um: {formality_de} ({ctx.deps.options}).
        
        Wichtige Regeln:
        - Behalte die ursprüngliche Bedeutung und alle Aussagen des Textes bei.
        - Behalte zwingend die Sprache des Ausgangstextes bei (ein englischer Text bleibt auf Englisch, ein französischer Text auf Französisch etc.).
        - Übersetze den Text nicht ins Deutsche.
        """
