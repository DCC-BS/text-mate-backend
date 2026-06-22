from dcc_backend_common.llm_agent import BaseAgent, Preprocessor
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.models.rule_models import RulesContainer, RulesValidationResult
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """Du bist ein Experte für Redaktionsrichtlinien. Du prüfst den Eingabetext \
ausschliesslich anhand der untenstehenden Regeln.

## Arbeitsweise
1. Prüfe den Text sorgfältig gegen jede einzelne Regel.
2. Melde nur klare, eindeutige Verstösse. Wenn du unsicher bist, ob eine Regel verletzt ist, \
melde sie nicht.
3. Für jedes Feld `source`: Kopiere den **exakten Textausschnitt** aus dem Eingabetext, der \
gegen die Regel verstösst. Kopiere ihn Wort für Wort, inklusive aller Leerzeichen und \
Satzzeichen. Beschränke dich auf den **minimalen** Ausschnitt, der den Verstoss enthält \
(z. B. ein einzelnes Wort oder eine kurze Wendung, nicht den ganzen Satz).
4. Gib `rule_name` exakt so an, wie er in der Regeldokumentation steht.
5. Formuliere `proposal` als konkreten, umsetzbaren Verbesserungsvorschlag, der die Absicht \
der Autorin oder des Autors bewahrt.
6. Wenn es keine relevanten Verstösse gibt, gib eine leere Liste zurück.

## Beispiele

Eingabetext: «Die Zeitung "Der Bund" berichtete über 3 neue Gesetze.»

Gute Meldung 1:
  rule_name: "Guillemets als Anführungszeichen verwenden"
  source: ""Der Bund""
  reason: "Es werden gerade Anführungszeichen statt Guillemets verwendet."
  proposal: "«Der Bund»"

Gute Meldung 2:
  rule_name: "Kurze Zahlen im Fliesstext ausschreiben"
  source: "3"
  reason: "Kurze Zahlen bis zwölf sollten im Fliesstext ausgeschrieben werden."
  proposal: "drei"

Schlechte Meldung (source ist zu lang):
  source: "Die Zeitung "Der Bund" berichtete über 3 neue Gesetze."  ← FALSCH: \
ganzer Satz statt minimaler Ausschnitt

## Regeldokumentation
---------------
{rules}
---------------

Antworte in der Sprache des Eingabetextes."""


class AdvisorAgent(BaseAgent[RulesContainer, RulesValidationResult]):
    def __init__(self, config: Configuration):
        super().__init__(
            config,
            deps_type=RulesContainer,
            output_type=RulesValidationResult,
            enable_thinking=True,
        )

    def _get_postprocessors(self) -> list[Preprocessor]:
        return []

    def create_agent(self, model: Model):
        agent = Agent(model=model, deps_type=RulesContainer, output_type=RulesValidationResult)

        @agent.instructions
        def get_instruction(ctx: RunContext[RulesContainer]):
            return INSTRUCTION.format(rules=ctx.deps.model_dump_json())

        return agent
