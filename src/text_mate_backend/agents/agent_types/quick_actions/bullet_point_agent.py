"""Bullet point agent for converting text to bullet points."""

from typing import override

from pydantic_ai import RunContext

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration


class BulletPointAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @property
    def agent_name(self) -> str:
        return "Bullet Point Agent"

    @property
    def agent_description(self) -> str:
        return "Converts text into a structured bullet point list highlighting the key statements"

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]):
        return """
            Du bist ein Assistent, der Text in eine übersichtliche Stichwortliste umwandelt.
            Erkenne die zentralen Aussagen und hebe sie hervor.

            Wandle den folgenden Text in eine strukturierte Stichwortliste um.
            Ordne Hauptgedanken und unterstützende Punkte sinnvoll an.
            Behalte zwingend die Sprache des Ausgangstextes bei und erstelle die Stichwortliste in der Sprache des Originaltextes.
            """
