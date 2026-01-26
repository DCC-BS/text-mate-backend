from typing import override

from dcc_backend_common.llm_agent import BaseAgent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.models.word_synonym_models import WordSynonymInput, WordSynonymResult
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """
You are an expert in language and synonyms. Your task is to find
synonyms for a given word in context of a document.

1. Find synonyms for a word in context of a document.
2. Provide a list of all synonyms found, minimum 1 word maximum 5 words.
3. If no synonyms are found, return an empty list.
4. The synonyms should be in the same language as a input word.
Word to find synonyms for:
---------------
{word}
---------------

Context:
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
