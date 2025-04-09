from pydantic import BaseModel


class WordSynonymInput(BaseModel):
    word: str
    context: str


class WordSynonymResult(BaseModel):
    synonyms: list[str]
