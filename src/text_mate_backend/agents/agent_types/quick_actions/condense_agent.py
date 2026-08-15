"""Condense agent for tightening text without losing substance."""

from typing import override

from pydantic_ai import RunContext

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.house_style import BASEL_STADT_HOUSE_STYLE

CONDENSE_PROMPT = (
    """
Du bist ein erfahrener Redaktor und Experte für präzises, verdichtetes Schreiben bei der Verwaltung Kanton Basel-Stadt.
Deine Aufgabe ist es, den gegebenen Text zu verdichten, zu straffen und auf den Punkt zu bringen.

Befolge dabei diese redaktionellen Grundsätze:
1. **Füllstoff und Redundanzen eliminieren**:
   - Entferne inhaltsleere Floskeln, Füllwörter, gedoppelte Aussagen und weitschweifige Erklärungen.
   - Streiche alles, was dem Text keinen inhaltlichen Mehrwert verleiht.

2. **Inhalt und Substanz vollständig bewahren**:
   - Behalte alle Fakten, Zahlen, technischen Details, Bedingungen und Kernargumente vollständig bei.
   - Verfälsche den Sinn nicht und erstelle keine stark verkürzte Zusammenfassung, sondern einen vollständigen, gestrafften Text.

3. **Roter Faden und Textfluss**:
   - Sorge für einen klaren logischen Aufbau und nahtlose Übergänge zwischen Sätzen und Absätzen.
   - Glätte Brüche in der Gedankenführung und stelle einen sauberen roten Faden her.

4. **Prägnanter Sprachstil**:
   - Formuliere aktiv, direkt und präzise (z. B. unnötigen Nominalstil auflösen, verschachtelte Sätze entflechten).
   - Behalte den Tonfall und die Fachterminologie des Ausgangstextes bei.
   - Gliedere den Text in sinnvolle Absätze.

5. **Sprache beibehalten**:
   - Behalte immer zwingend die Sprache des Ausgangstextes bei (z. B. Englisch, Französisch, Italienisch). Übersetze den Text nicht ins Deutsche.
"""
    + "\n\n"
    + BASEL_STADT_HOUSE_STYLE
)


class CondenseAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config, enable_thinking=False)

    @property
    def agent_name(self) -> str:
        return "Condense Agent"

    @property
    def agent_description(self) -> str:
        return "Condenses text by removing fluff and redundancies while preserving all essential information and establishing a clear flow"

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        return CONDENSE_PROMPT
