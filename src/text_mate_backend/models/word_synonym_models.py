from pydantic import BaseModel, Field


class WordSynonymInput(BaseModel):
    word: str = Field(description="The word to find a synonym for")
    context: str = Field(description="The sentence in which the word is used.")


class WordSynonymResult(BaseModel):
    synonyms: list[str] = Field(description="A list of alternative words, in the same language as a input word")
