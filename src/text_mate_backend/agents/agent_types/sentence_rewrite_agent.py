from typing import override

from pydantic_ai import Agent
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_types.quick_actions.formality_agent import RunContext
from text_mate_backend.agents.base import BaseAgent
from text_mate_backend.models.sentence_rewrite_model import SentenceRewriteInput, SentenceRewriteResult
from text_mate_backend.utils.auth_settings import Configuration

INSTRUCTION = """
You are an expert in language and rewriting. Your task is to generate
alternative ways to express a sentence or a section in a given context.

1. Generate at least 1 but maximum of 5 alternative rewrites for a given sentence.
2. The rewrites should be in the same language as a input text.
3. The rewrites should be different from the original sentence.
4. The rewrites should be relevant to the context provided.
5. Only rewrite a given sentence, not the entire context.

Sentence to rewrite:
---------------
{sentence}
---------------

Context:
---------------
{context}
---------------

Return your response with:
- sentence: the original sentence that was rewritten
- options: a list of alternative rewrites
"""


class SentenceRewriteAgent(BaseAgent[SentenceRewriteInput, SentenceRewriteResult]):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_agent(self, model: Model) -> Agent[SentenceRewriteInput, SentenceRewriteResult]:
        agent = Agent(model=model, deps_type=SentenceRewriteInput, output_type=SentenceRewriteResult)

        @agent.instructions
        def get_instruction(ctx: RunContext[SentenceRewriteInput]):
            return INSTRUCTION.format(sentence=ctx.deps.sentence, context=ctx.deps.context)

        return agent
