"""English analyzer: Flesch Reading Ease, mapped to CEFR.

Ported from ``blokkli/editor``'s ``SCORE_CONFIGS.en`` (MIT): FRE coefficients
from ``@lunarisapp/readability``, bands aligned to CEFR buckets (easy = A1-B2,
FRE >= 60; ok = C1; hard = C2), impact thresholds ``[40, 25, 10]`` and
``minWords`` 15.

The one thing blokkli outsources is syllable counting (npm ``syllable``); here
that is ``pyphen``, which hyphenates rather than syllabifies. FRE is sensitive
to syllable counts, so English scores are the least trustworthy of the four
languages -- see ``docs/simplify_redesign.md`` section 11.
"""

from collections.abc import Sequence
from typing import final

import pyphen

from text_mate_backend.readability.core.bands import (
    build_agent_context,
    build_scale_info,
    classify_band,
    impact_for_score,
)
from text_mate_backend.readability.core.formulas import (
    FleschCoefficients,
    flesch_reading_ease,
    round_score,
    safe_score,
)
from text_mate_backend.readability.core.tokenize import (
    avg_sentence_length,
    avg_syllables_per_word,
    segment_words,
)
from text_mate_backend.readability.types import (
    BandConfig,
    ImpactLevel,
    LanguageCode,
    ReadabilityBand,
    ReferenceRow,
    ScaleInfo,
)

MIN_WORDS = 15

#: Per-language FRE coefficients from @lunarisapp/readability (MIT).
FRE_COEFFICIENTS = FleschCoefficients(base=206.835, sentences=1.015, syllables_per_word=84.6)

BAND_CONFIG = BandConfig(
    direction="higher_easier",
    easy=60.0,
    ok=50.0,
    impact_thresholds=(40.0, 25.0, 10.0),
)

REFERENCE_TABLE: tuple[ReferenceRow, ...] = (
    ReferenceRow("FRE 90–100", "A1 — beginners"),
    ReferenceRow("FRE 80–90", "A2 — elementary"),
    ReferenceRow("FRE 70–80", "B1 — intermediate"),
    ReferenceRow("FRE 60–70", "B2 — upper intermediate (target)"),
    ReferenceRow("FRE 50–60", "C1 — advanced (could be simpler)"),
    ReferenceRow("FRE 0–50", "C2 — mastery — this is what gets flagged"),
)

_HYPHENATION_LANGUAGE = "en_US"
_dictionary: pyphen.Pyphen | None = None


def _hyphenation_dictionary() -> pyphen.Pyphen:
    """Load the hyphenation dictionary once, on first use."""
    global _dictionary
    if _dictionary is None:
        _dictionary = pyphen.Pyphen(lang=_HYPHENATION_LANGUAGE)
    return _dictionary


def count_syllables_en(word: str) -> int:
    """Approximate the syllable count of an English word via hyphenation points.

    >>> count_syllables_en("readability") >= 3
    True
    >>> count_syllables_en("cat")
    1
    """
    if not word:
        return 0
    return max(1, len(_hyphenation_dictionary().inserted(word).split("-")))


def flesch_to_cefr(score: float) -> str:
    """Flesch Reading Ease -> CEFR bucket (Linguapress correspondence table).

    Approximate by construction: FRE only measures sentence length and
    syllables per word, so short sentences with advanced vocabulary land in a
    lower-than-expected bucket.

    >>> [flesch_to_cefr(s) for s in (95, 85, 75, 65, 55, 45)]
    ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    """
    if score >= 90:
        return "A1"
    if score >= 80:
        return "A2"
    if score >= 70:
        return "B1"
    if score >= 60:
        return "B2"
    if score >= 50:
        return "C1"
    return "C2"


@final
class EnglishAnalyzer:
    """Flesch Reading Ease analyzer for English."""

    language: LanguageCode = "en"
    #: blokkli labels the English metric by what it is reported as, not by the
    #: formula behind it.
    score_label: str = "CEFR"
    min_words: int = MIN_WORDS

    def score(self, text: str) -> float | None:
        stripped = text.strip()
        if not stripped or len(segment_words(stripped)) < self.min_words:
            return None

        value = safe_score(
            lambda: flesch_reading_ease(
                avg_sentence_length(stripped),
                avg_syllables_per_word(stripped, count_syllables_en),
                FRE_COEFFICIENTS,
            )
        )
        return round_score(value) if value is not None else None

    def band(self, score: float) -> ReadabilityBand:
        return classify_band(score, BAND_CONFIG)

    def impact(self, score: float) -> ImpactLevel:
        return impact_for_score(score, BAND_CONFIG)

    def cefr(self, score: float) -> str | None:
        return flesch_to_cefr(score)

    def format_score(self, score: float) -> str:
        return f"{flesch_to_cefr(score)} (FRE {score:.1f})"

    def agent_context(self) -> str:
        return build_agent_context(self.score_label, REFERENCE_TABLE)

    def reference_table(self) -> Sequence[ReferenceRow]:
        return REFERENCE_TABLE

    def scale_info(self) -> ScaleInfo:
        return build_scale_info(BAND_CONFIG)
