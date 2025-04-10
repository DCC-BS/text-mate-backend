from typing import Callable, TypeVar

import dspy  # type: ignore
from returns.result import safe

from text_mate_backend.services.dspy_facade import DspyFacade, DspyInitOptions
from text_mate_backend.utils.logger import get_logger

T = TypeVar("T")

logger = get_logger("sentence_rewrite_service")


class SentenceRewriteSignature(dspy.Signature):
    """
    Generate alternative ways to express a sentence in the given context.
    """

    sentence: str = dspy.InputField(desc="The sentence to rewrite")
    context: str = dspy.InputField(desc="The surrounding context for the sentence")
    min_options: int = dspy.InputField(desc="The minimum number of alternatives to generate")
    max_options: int = dspy.InputField(desc="The maximum number of alternatives to generate")
    options: list[str] = dspy.OutputField(desc="A list of alternative sentence rewrites")


class SentenceRewriteService:
    """Service for rewriting sentences with alternative options."""

    def __init__(self, dspy_facade_factory: Callable[[], DspyFacade]) -> None:
        """
        Initialize the sentence rewrite service.

        Args:
            dspy_facade_factory: Factory function to create DSPy facade instances
        """
        self.dspy_facade: DspyFacade = dspy_facade_factory(
            options=DspyInitOptions(
                temperature=0.6,
                max_tokens=1000,
            )
        )
        logger.info("Sentence rewrite service initialized")

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

        # Generate at least 3 but maximum of 5 alternative rewrites
        result: SentenceRewriteSignature = self.dspy_facade.predict(
            SentenceRewriteSignature, sentence=sentence, context=context, min_options=3, max_options=5
        )

        # Filter out empty options or options identical to the original
        valid_options = [option for option in result.options if option and option.strip() != sentence.strip()]
        return valid_options
