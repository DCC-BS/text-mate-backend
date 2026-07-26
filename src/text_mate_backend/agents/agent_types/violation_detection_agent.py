from dcc_backend_common.llm_agent import BaseAgent, Preprocessor
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_utils import build_agent_metadata
from text_mate_backend.models.rule_models import DetectionResult, RulesContainer
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """Du bist ein Experte für Redaktionsrichtlinien. Du prüfst den Eingabetext \
ausschliesslich anhand der untenstehenden Regeln. In diesem Schritt geht es nur darum, \
Verstösse zu **finden** — du generierst keine Verbesserungsvorschläge.

## Arbeitsweise
1. Prüfe den Text sorgfältig gegen jede einzelne Regel.
2. Für jedes Feld `source`: Kopiere den **exakten Textausschnitt** aus dem Eingabetext, der \
gegen die Regel verstösst. Kopiere ihn Wort für Wort, inklusive aller Leerzeichen und \
Satzzeichen. Beschränke dich auf den **minimalen** Ausschnitt, der den Verstoss enthält \
(z. B. ein einzelnes Wort oder eine kurze Wendung, nicht den ganzen Satz).
3. Gib `rule_name` exakt so an, wie er in der Regeldokumentation steht.
4. Formuliere `reason` als kurze Beschreibung, **warum** der Textausschnitt gegen die Regel \
verstösst. Kein Verbesserungsvorschlag hier — der folgt in einem separaten Schritt.
5. Wenn es keine relevanten Verstösse gibt, gib eine leere Liste zurück.

Die Regeln haben follgendes Format:
---------------
{input_model_description}
---------------

## Regeldokumentation
---------------
{rules}
---------------

## Output Format
Generiere deine Antwort ensprechen diesem Schema:
---------------
{output_model_description}
---------------

## Beispiele

Eingabetext: «Die Zeitung "Der Bund" berichtete über 3 neue Gesetze.»

Gute Meldung 1:
  rule_name: "Guillemets als Anführungszeichen verwenden"
  source: ""Der Bund""
  reason: "Es werden gerade Anführungszeichen statt Guillemets verwendet."

Gute Meldung 2:
  rule_name: "Kurze Zahlen im Fliesstext ausschreiben"
  source: "3"
  reason: "Kurze Zahlen bis zwölf sollten im Fliesstext ausgeschrieben werden."

Antworte in der Sprache des Eingabetextes."""


class ViolationDetectionAgent(BaseAgent[RulesContainer, DetectionResult]):
    def __init__(self, config: Configuration):
        super().__init__(
            config,
            deps_type=RulesContainer,
            output_type=DetectionResult,
            enable_thinking=True,
        )

    def _get_postprocessors(self) -> list[Preprocessor]:
        return []

    def create_agent(self, model: Model):
        agent = Agent(
            model=model,
            deps_type=RulesContainer,
            output_type=DetectionResult,
            name="Violation Detection Agent",
            description="Detects violations of editorial rules in a text and returns structured findings",
            metadata=lambda ctx: build_agent_metadata(
                "violation_detection",
                enable_thinking=True,
                output_type="DetectionResult",
                rule_count=len(ctx.deps.rules),
                rule_collections=sorted(ctx.deps.document_names),
            ),
        )

        @agent.instructions
        def get_instruction(ctx: RunContext[RulesContainer]):
            return INSTRUCTION.format(
                rules=ctx.deps.model_dump_json(),
                input_model_description=RulesContainer.model_json_schema(),
                output_model_description=DetectionResult.model_json_schema(),
            )

        return agent
