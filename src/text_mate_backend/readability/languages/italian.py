"""Italian analyzer: Gulpease index.

Ported verbatim from ``blokkli/editor``'s ``SCORE_CONFIGS.it`` (MIT): Gulpease
with bands easy >= 80 / ok >= 60, impact thresholds ``[60, 50, 40]``,
``minWords`` 5 and the reference table below. Gulpease needs no syllables and
has no CEFR mapping, so ``cefr()`` returns None.
"""

from collections.abc import Sequence
from typing import final

from text_mate_backend.readability.core.bands import (
    build_agent_context,
    build_scale_info,
    classify_band,
    impact_for_score,
)
from text_mate_backend.readability.core.formulas import gulpease_index, round_score, safe_score
from text_mate_backend.readability.core.tokenize import (
    char_count,
    segment_words,
    sentence_count,
    word_count,
)
from text_mate_backend.readability.types import (
    BandConfig,
    ImpactLevel,
    LanguageCode,
    ReadabilityBand,
    ReferenceRow,
    ScaleInfo,
)

MIN_WORDS = 5

BAND_CONFIG = BandConfig(
    direction="higher_easier",
    easy=80.0,
    ok=60.0,
    impact_thresholds=(60.0, 50.0, 40.0),
)

REFERENCE_TABLE: tuple[ReferenceRow, ...] = (
    ReferenceRow("Above 80", "Very easy (children's books)"),
    ReferenceRow("60–80", "Easy (simple articles)"),
    ReferenceRow("50–60", "Medium (newspapers)"),
    ReferenceRow("40–50", "Difficult (official documents)"),
    ReferenceRow("Below 40", "Very difficult — this is what gets flagged"),
    ReferenceRow("Below 30", "Critical — must be simplified"),
)


@final
class ItalianAnalyzer:
    """Gulpease analyzer for Italian."""

    language: LanguageCode = "it"
    score_label: str = "Gulpease"
    min_words: int = MIN_WORDS

    def score(self, text: str) -> float | None:
        stripped = text.strip()
        if not stripped or len(segment_words(stripped)) < self.min_words:
            return None

        value = safe_score(
            lambda: gulpease_index(
                sentence_count(stripped),
                char_count(stripped),
                word_count(stripped),
            )
        )
        return round_score(value) if value is not None else None

    def band(self, score: float) -> ReadabilityBand:
        return classify_band(score, BAND_CONFIG)

    def impact(self, score: float) -> ImpactLevel:
        return impact_for_score(score, BAND_CONFIG)

    def cefr(self, score: float) -> str | None:
        """Gulpease has no CEFR correspondence table."""
        return None

    def format_score(self, score: float) -> str:
        return f"Gulpease {score:.1f}"

    def agent_context(self) -> str:
        return build_agent_context(self.score_label, REFERENCE_TABLE)

    def reference_table(self) -> Sequence[ReferenceRow]:
        return REFERENCE_TABLE

    def scale_info(self) -> ScaleInfo:
        return build_scale_info(BAND_CONFIG)
