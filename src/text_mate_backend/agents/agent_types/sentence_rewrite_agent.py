from typing import override

from dcc_backend_common.llm_agent import BaseAgent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.models.sentence_rewrite_model import SentenceRewriteInput, SentenceRewriteResult
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """
Du bist ein Experte für Sprache und Umformulierung. Deine Aufgabe ist es,
alternative Formulierungen für einen Satz oder Abschnitt in einem gegebenen Kontext zu erzeugen.

1. Erzeuge mindestens 1 und höchstens 5 alternative Umformulierungen für den gegebenen Satz.
2. Die Umformulierungen sollen in derselben Sprache wie der Eingabetext sein.
3. Die Umformulierungen sollen sich vom ursprünglichen Satz unterscheiden.
4. Die Umformulierungen sollen zum gegebenen Kontext passen.
5. Formuliere nur den gegebenen Satz um, nicht den gesamten Kontext.

Umzuformulierender Satz:
---------------
{sentence}
---------------

Kontext:
---------------
{context}
---------------

Gib deine Antwort mit folgenden Feldern zurück:
- sentence: der ursprüngliche Satz, der umformuliert wurde
- options: eine Liste alternativer Umformulierungen
"""


class SentenceRewriteAgent(BaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config, deps_type=SentenceRewriteInput, output_type=SentenceRewriteResult)

    @override
    def create_agent(self, model: Model) -> Agent[SentenceRewriteInput, SentenceRewriteResult]:
        agent = Agent[SentenceRewriteInput, SentenceRewriteResult](
            model=model, deps_type=SentenceRewriteInput, output_type=SentenceRewriteResult
        )

        @agent.instructions
        def get_instruction(ctx: RunContext[SentenceRewriteInput]):
            return INSTRUCTION.format(sentence=ctx.deps.sentence, context=ctx.deps.context)

        return agent
