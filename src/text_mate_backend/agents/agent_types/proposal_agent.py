from dcc_backend_common.llm_agent import BaseAgent, Preprocessor
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_utils import build_agent_metadata
from text_mate_backend.models.rule_models import ProposalRequest
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """Du bist ein Experte für Redaktionsrichtlinien. In einem vorherigen Schritt \
wurde ein Verstoss gegen eine Regel gefunden. Deine einzige Aufgabe ist es nun, einen \
**konkreten, umsetzbaren Verbesserungsvorschlag** zu formulieren.

## Arbeitsweise
1. Lies die Regel, den Verstoss (`source`), die Begründung (`reason`) und den Kontextsatz.
2. Formuliere `proposal` als konkreten Ersatz für den `source`-Ausschnitt, der die Absicht \
der Autorin oder des Autors bewahrt und die Regel erfüllt.
3. Der Vorschlag muss sprachlich und grammatikalisch in den Kontextsatz passen.
4. Gib ausschliesslich den Vorschlag als reinen Text aus — keine Erklärung, kein Markdown, \
keine Anführungszeichen, kein Einleitungstext.

## Regel
---------------
{rule}
---------------

## Verstoss (source)
---------------
{source}
---------------

## Begründung (reason)
---------------
{reason}
---------------

## Kontextsatz
---------------
{context_sentence}
---------------

Antworte in der Sprache des Eingabetextes."""


class ProposalAgent(BaseAgent[ProposalRequest, str]):
    def __init__(self, config: Configuration):
        super().__init__(
            config,
            deps_type=ProposalRequest,
            output_type=str,
            enable_thinking=False,
        )

    def _get_postprocessors(self) -> list[Preprocessor]:
        return []

    def create_agent(self, model: Model):
        agent = Agent(
            model=model,
            deps_type=ProposalRequest,
            output_type=str,
            name="Proposal Agent",
            description="Generates a concrete, actionable improvement proposal for a single editorial rule violation",
            metadata=lambda ctx: build_agent_metadata(
                "proposal",
                output_type="str",
                rule_name=ctx.deps.rule.name,
                source_length=len(ctx.deps.source),
                context_length=len(ctx.deps.context_sentence),
            ),
        )

        @agent.instructions
        def get_instruction(ctx: RunContext[ProposalRequest]):
            deps = ctx.deps
            return INSTRUCTION.format(
                rule=deps.rule.model_dump_json(),
                source=deps.source,
                reason=deps.reason,
                context_sentence=deps.context_sentence,
            )

        return agent
