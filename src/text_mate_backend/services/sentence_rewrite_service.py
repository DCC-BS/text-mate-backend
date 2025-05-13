from typing import TypeVar

from llama_index.core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from returns.result import safe

from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

T = TypeVar("T")

logger = get_logger("sentence_rewrite_service")


class SentenceRewriteOutput(BaseModel):
    options: list[str] = Field(
        description="A list of alternative sentence or section rewrites, in the same language as the input text"
    )


class SentenceRewriteService:
    """Service for rewriting sentences with alternative options."""

    def __init__(self, llm_facade: LLMFacade) -> None:
        self.llm_facade = llm_facade

    @safe
    def rewrite_sentence(self, sentence: str, context: str) -> list[str]:
        """
        Generate alternative rewrite options for a sentence based on context.

        Args:
            sentence: The sentence to rewrite
            context: The surrounding text context

        Returns:
            Result containing list of rewrite options or an exception
        """
        logger.info("Generating sentence rewrites", sentence=sentence)

        result = self.llm_facade.structured_predict(
            SentenceRewriteOutput,
            PromptTemplate(
                """You are an expert in language and rewriting. Your task is to generate alternative ways to express a sentence or a section in the given context.

                1. Generate at least 1 but maximum of 5 alternative rewrites for the given sentence.
                2. The rewrites should be in the same language as the input text.
                3. The rewrites should be different from the original sentence.
                4. The rewrites should be relevant to the context provided.

                Sentence to rewrite:
                {sentence}
                Context:
                {context}
                """
            ),
            sentence=sentence,
            context=context,
        )

        # Filter out empty options or options identical to the original
        valid_options = [option for option in result.options if option and option.strip() != sentence.strip()]
        return valid_options
