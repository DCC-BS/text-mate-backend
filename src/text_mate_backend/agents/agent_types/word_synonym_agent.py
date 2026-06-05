from typing import override

from dcc_backend_common.llm_agent import BaseAgent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.models.word_synonym_models import WordSynonymInput, WordSynonymResult
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """
Du bist ein Experte für Sprache und Synonyme. Deine Aufgabe ist es,
Synonyme für ein gegebenes Wort im Kontext eines Dokuments zu finden.

1. Finde Synonyme für ein Wort im Kontext des Dokuments.
2. Gib eine Liste aller gefundenen Synonyme aus, mindestens 1 und höchstens 5 Wörter.
3. Findest du keine Synonyme, gib eine leere Liste zurück.
4. Die Synonyme sollen in derselben Sprache wie das Eingabewort sein.

Wort, für das Synonyme gesucht werden:
---------------
{word}
---------------

Kontext:
---------------
{context}
---------------
"""


class WordSynonymAgent(BaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config, deps_type=WordSynonymInput, output_type=WordSynonymResult)

    @override
    def create_agent(self, model: Model) -> Agent[WordSynonymInput, WordSynonymResult]:
        agent = Agent[WordSynonymInput, WordSynonymResult](
            model=model, deps_type=WordSynonymInput, output_type=WordSynonymResult
        )

        @agent.instructions
        def get_instruction(ctx: RunContext[WordSynonymInput]):
            return INSTRUCTION.format(word=ctx.deps.word, context=ctx.deps.context)

        return agent
