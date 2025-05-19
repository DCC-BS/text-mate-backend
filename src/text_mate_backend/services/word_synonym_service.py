from typing import final

from llama_index.core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from returns.result import safe

from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("word_synonym_service")


class SynonymOutput(BaseModel):
    options: list[str] = Field(
        description="A list of alternative words, in the same language as the input word",
    )


@final
class WordSynonymService:
    def __init__(self, llm_facade: LLMFacade) -> None:
        self.llm_facade = llm_facade

    @safe
    def get_synonyms(self, word: str, context: str) -> list[str]:
        """
        Get synonyms for a word in the context of a document.
        """
        logger.info("Getting synonyms for word: %s", word)

        response = self.llm_facade.structured_predict(
            SynonymOutput,
            PromptTemplate(
                """You are an expert in language and synonyms. Your task is to find synonyms for the given word in the context of the document.

                1. Find synonyms for the word in the context of the document.
                2. Provide a list of all synonyms found, minimum 1 word maximus 5 words.
                3. If no synonyms are found, return an empty list.
                4. The synonyms should be in the same language as the input word.
                Word to find synonyms for:
                ---------------
                {word}
                ---------------

                Context:
                ---------------
                {context}
                ---------------
                """,
            ),
            word=word,
            context=context,
        )

        return response.options
