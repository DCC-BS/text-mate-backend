from pydantic import BaseModel, Field

from text_mate_backend.readability.types import ReadabilityBand


class TextAnalysisInput(BaseModel):
    text: str = Field(description="Text to analyze for understandability (German unless detected otherwise)")


class TextAnalysisResult(BaseModel):
    """Result of ``POST /text-analysis``.

    ``zix_score`` and ``cefr_level`` are the original, German-specific fields and
    keep their meaning: the existing frontend CEFR badge reads them. The
    language-aware fields below were added on top — ``score``/``score_label``/
    ``band`` describe whichever metric was used, so for German they mirror
    ``zix_score``/``"ZIX"``, and for French or Italian ``zix_score`` and
    ``cefr_level`` are null because those metrics have no CEFR mapping.

    A text in a language with no analyzer (Spanish, Chinese, ...) reports that
    language with *every* score field null: an invented number would be worse
    than none.
    """

    zix_score: float | None = Field(default=None, description="ZIX understandability score (-10 to 10); None if text is too short")
    cefr_level: str | None = Field(default=None, description="CEFR level (A1–C2); None if score could not be computed")
    language: str | None = Field(
        default=None,
        description=(
            "Detected language of the text (ISO 639-1), including languages that cannot be scored. "
            "Null when detection was inconclusive; the text is then scored as German by default."
        ),
    )
    score: float | None = Field(default=None, description="Raw score of the language's metric")
    score_label: str | None = Field(default=None, description='Metric name ("ZIX", "CEFR", "LIX", "Gulpease")')
    band: ReadabilityBand | None = Field(default=None, description="Calibrated band: easy | ok | hard")
