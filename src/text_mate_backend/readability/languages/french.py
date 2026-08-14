"""French analyzer: LIX (Läsbarhetsindex).

Ported verbatim from ``blokkli/editor``'s ``SCORE_CONFIGS.fr`` (MIT): LIX with
bands easy <= 40 / ok <= 59, impact thresholds ``[50, 60, 70]``, ``minWords`` 5
and the reference table below. LIX needs no syllables. There is no CEFR mapping
for LIX, so ``cefr()`` returns None.
"""

from collections.abc import Sequence
from typing import final

from text_mate_backend.readability.core.bands import (
    build_agent_context,
    build_scale_info,
    classify_band,
    impact_for_score,
)
from text_mate_backend.readability.core.formulas import lix, round_score, safe_score
from text_mate_backend.readability.core.tokenize import (
    avg_words_per_sentence,
    long_word_count,
    segment_words,
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
    direction="higher_harder",
    easy=40.0,
    ok=59.0,
    impact_thresholds=(50.0, 60.0, 70.0),
)

REFERENCE_TABLE: tuple[ReferenceRow, ...] = (
    ReferenceRow("Below 25", "Very easy (children's books)"),
    ReferenceRow("25–40", "Easy (simple articles)"),
    ReferenceRow("40–50", "Medium (newspapers)"),
    ReferenceRow("50–60", "Difficult (official documents)"),
    ReferenceRow("Above 60", "Very difficult — this is what gets flagged"),
    ReferenceRow("Above 70", "Critical — must be simplified"),
)


@final
class FrenchAnalyzer:
    """LIX analyzer for French."""

    language: LanguageCode = "fr"
    score_label: str = "LIX"
    min_words: int = MIN_WORDS

    def score(self, text: str) -> float | None:
        stripped = text.strip()
        if not stripped or len(segment_words(stripped)) < self.min_words:
            return None

        value = safe_score(
            lambda: lix(
                word_count(stripped),
                long_word_count(stripped),
                avg_words_per_sentence(stripped),
            )
        )
        return round_score(value) if value is not None else None

    def band(self, score: float) -> ReadabilityBand:
        return classify_band(score, BAND_CONFIG)

    def impact(self, score: float) -> ImpactLevel:
        return impact_for_score(score, BAND_CONFIG)

    def cefr(self, score: float) -> str | None:
        """LIX has no CEFR correspondence table."""
        return None

    def format_score(self, score: float) -> str:
        return f"LIX {score:.1f}"

    def agent_context(self) -> str:
        return build_agent_context(self.score_label, REFERENCE_TABLE)

    def reference_table(self) -> Sequence[ReferenceRow]:
        return REFERENCE_TABLE

    def scale_info(self) -> ScaleInfo:
        return build_scale_info(BAND_CONFIG)
