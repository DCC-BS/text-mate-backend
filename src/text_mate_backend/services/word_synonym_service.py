from typing import Callable, final

import dspy  # type: ignore
from returns.result import safe

from text_mate_backend.services.dspy_facade import DspyFacade, DspyInitOptions
from text_mate_backend.utils.logger import get_logger

logger = get_logger("word_synonym_service")


class SynonymSignature(dspy.Signature):
    """
    Find synonyms for a word in the context of a document.
    """

    word: str = dspy.InputField(desc="The word to find synonyms for")
    context: str = dspy.InputField(desc="The sentence or paragraph containing the word")
    options: list[str] = dspy.OutputField(desc="A list of alternative words, in the same language as the input word")


@final
class WordSynonymService:
    def __init__(self, dspy_facade_factory: Callable[..., DspyFacade]) -> None:
        logger.info("Initializing WordSynonymService")
        self.dspy_facade: DspyFacade = dspy_facade_factory(
            options=DspyInitOptions(
                temperature=0.6,
                max_tokens=1000,
            )
        )
        logger.info("WordSynonymService initialized successfully")

    @safe
    def get_synonyms(self, word: str, context: str) -> list[str]:
        """
        Get synonyms for a word in the context of a document.
        """
        logger.info("Getting synonyms for word: %s", word)
        response: SynonymSignature = self.dspy_facade.predict(SynonymSignature, word=word, context=context)

        return response.options
