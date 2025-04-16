from typing import Annotated, List, final

from pydantic import BaseModel, Field


class CorrectionInput(BaseModel):
    text: Annotated[str, "The text to be corrected"]
    language: Annotated[str, "The language of the text"] = "auto"


@final
class TextCorrectionOptions:
    def __init__(
        self, language: str = "auto", writing_style: str = "simple", tone: str = "neutral", formality: str = "formal"
    ) -> None:
        """
        language: str
        writing_style: simple, buisiness, academic, casual, technical, legal, medical, scientific, etc.
        tone: Enthusiastic, neutral, friendly, confident, diplomatic, etc.
        formality: formal, informal, neutral, etc.
        """
        self.language: str = language
        self.writing_style: str = writing_style
        self.tone: str = tone
        self.formality: str = formality


class CorrectionBlock(BaseModel):
    original: Annotated[str, "The original text"]
    corrected: Annotated[List[str], "The corrected text"]
    offset: int
    length: int
    explanation: Annotated[str, "A short explanation of the correction use the language of the original text"]


class CorrectionBlocks(BaseModel):
    blocks: list[CorrectionBlock]


class CorrectionResult(BaseModel):
    original: str
    blocks: list[CorrectionBlock]


correction_blocks_json_schema = CorrectionBlocks.model_json_schema()
