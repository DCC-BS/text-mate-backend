from pydantic import BaseModel


class SentenceRewriteInput(BaseModel):
    sentence: str
    context: str


class SentenceRewriteResult(BaseModel):
    options: list[str]
