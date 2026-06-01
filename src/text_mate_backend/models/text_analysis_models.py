from pydantic import BaseModel, Field


class TextAnalysisInput(BaseModel):
    text: str = Field(description="German text to analyze for understandability")


class TextAnalysisResult(BaseModel):
    zix_score: float | None = Field(description="ZIX understandability score (-10 to 10); None if text is too short")
    cefr_level: str | None = Field(description="CEFR level (A1–C2); None if score could not be computed")
