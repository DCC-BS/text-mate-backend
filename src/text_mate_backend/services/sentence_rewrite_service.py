from typing import TypeVar

from pydantic import BaseModel, Field
from returns.result import safe

from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.logger import get_logger

T = TypeVar("T")

logger = get_logger("sentence_rewrite_service")


class SentenceRewriteOutput(BaseModel):
    options: list[str] = Field(
        description="A list of alternative sentence or section rewrites, in the same language as a input text"
    )


class SentenceRewriteService:
    """Service for rewriting sentences with alternative options."""

    def __init__(self, llm_facade: PydanticAIAgent) -> None:
        self.llm_facade = llm_facade

    @safe
    async def rewrite_sentence(self, sentence: str, context: str) -> list[str]:
        """
        Generate alternative rewrite options for a sentence based on context.

        Args:
            sentence: The sentence to rewrite
            context: The surrounding text context

        Returns:
            Result containing list of rewrite options or an exception
        """
        prompt = f"""You are an expert in language and rewriting. Your task is to generate
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
                """

        result = await self.llm_facade.structured_predict(
            SentenceRewriteOutput,
            prompt,
            sentence=sentence,
            context=context,
        )

        # Filter out empty options or options identical to the original
        valid_options = [option for option in result.options if option and option.strip() != sentence.strip()]
        return valid_options
