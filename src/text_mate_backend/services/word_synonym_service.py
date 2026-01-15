from typing import final

from pydantic import BaseModel, Field
from returns.result import safe

from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.logger import get_logger

logger = get_logger("word_synonym_service")


class SynonymOutput(BaseModel):
    options: list[str] = Field(
        description="A list of alternative words, in the same language as a input word",
    )


@final
class WordSynonymService:
    def __init__(self, llm_facade: PydanticAIAgent) -> None:
        self.llm_facade = llm_facade

    @safe
    async def get_synonyms(self, word: str, context: str) -> list[str]:
        """
        Get synonyms for a word in context of a document.
        """

        prompt = f"""You are an expert in language and synonyms. Your task is to find
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

        response = await self.llm_facade.structured_predict(
            SynonymOutput,
            prompt,
            word=word,
            context=context,
        )

        return response.options
