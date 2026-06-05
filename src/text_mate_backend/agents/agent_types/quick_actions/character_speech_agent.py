from typing import override

from pydantic_ai import RunContext

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration

from .quick_action_base_agent import QuickActionBaseAgent

INSTRUCTION = """
Du bist ein Spezialist für die Umwandlung von Text zwischen direkter und indirekter Rede.

{sub_instructions}

## Andere Sprachen:
Der Fokus liegt auf Deutsch. Ist der Eingabetext nicht auf Deutsch, wende die entsprechenden Regeln der jeweiligen Sprache an:
- Englisch: reported speech mit backshift (Präsens → Präteritum, Präteritum → Plusquamperfekt)
- Französisch: discours indirect (concordance des temps)
- Spanisch: estilo indirecto

Gib nur den umgewandelten Text aus, ohne Erklärungen oder Kommentare.
"""

DIRECT_INSTRUCTION = """
Aufgabe: Wandle den gegebenen Text in direkte Rede um.

## Regeln für die direkte Rede:
- Verwende Anführungszeichen: «...» oder »...«
- Behalte die ursprünglichen Pronomen und Zeitformen bei.
- Gib die genauen Worte der sprechenden Person wieder.
- Verwende Frage- und Ausrufezeichen wie im Original.

# Beispiele
Sie sagt, dass sie das Haus kaufen wolle.
→ «Ich kaufe das Haus», sagt sie.

Er fragt, ob ich zum Fussball gehen möchte.
→ «Möchtest du zum Fussball gehen?», fragt er.
"""

INDIRECT_INSTRUCTIONS = """
Aufgabe: Wandle den gegebenen Text in indirekte Rede um.

## Regeln für die indirekte Rede:
- Entferne die Anführungszeichen.
- Passe die Pronomen an: ich → er/sie, du → er/sie, mein → sein/ihr usw.
- Verwende für die Wiedergabe den Konjunktiv I: er sage, sie gehe, er habe.
- Stimmt der Konjunktiv I mit dem Indikativ überein, verwende den Konjunktiv II: er ginge, er hätte.
- Verwende bei Fragen ein Fragewort: ob, wann, wo, warum.
- Wandle den Satz in einen Nebensatz um.
- Ergänze einen einleitenden Hauptsatz: dass-Satz oder w-Frage.

# Beispiele
«Ich komme morgen», sagt sie.
→ Sie sagt, dass sie morgen komme.

«Wann kommst du?», fragt er mich.
→ Er fragt mich, wann ich komme.

«Wir haben das Buch gelesen», berichten sie.
→ Sie berichten, dass sie das Buch gelesen hätten.
"""


class CharacterSpeechAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config, enable_thinking=False)

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        sub_instructions = DIRECT_INSTRUCTION if ctx.deps.options == "direct_speech" else INDIRECT_INSTRUCTIONS

        return INSTRUCTION.format(sub_instructions=sub_instructions)
