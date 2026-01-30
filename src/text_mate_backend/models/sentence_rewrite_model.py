from pydantic import BaseModel, field_validator


class SentenceRewriteInput(BaseModel):
    sentence: str
    context: str


class SentenceRewriteResult(BaseModel):
    sentence: str
    options: list[str]

    @field_validator("options", mode="before")
    @classmethod
    def filter_options(cls, v, info):
        sentence = info.data.get("sentence", "")
        return [opt for opt in v if opt and opt.strip() != sentence.strip()]
