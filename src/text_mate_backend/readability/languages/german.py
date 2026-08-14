"""German analyzer: ZIX understandability index.

German is the one language that does *not* use a hand formula. ZIX is a trained
model (spaCy ``de_core_news_sm`` features -> StandardScaler -> ridge regressor,
clipped to [-10, 10]) with vocabulary difficulty in its feature set, which makes
it far harder to game than a syllable-counting formula. blokkli's Wiener
Sachtextformel is therefore deliberately not ported.

Calibration comes from ZIX itself and from
``machinelearningZH/simply-simplify-language``'s ``config.yaml``
(``limit_hard: 0``, ``limit_medium: -2``): CEFR in {A1, A2, B1} <=> ZIX >= 0,
which is exactly the "easy" floor used for Einfache Sprache.
"""

import warnings
from collections.abc import Sequence
from typing import final

from text_mate_backend.readability.core.bands import (
    build_agent_context,
    build_scale_info,
    classify_band,
    impact_for_score,
)
from text_mate_backend.readability.core.formulas import round_score
from text_mate_backend.readability.core.tokenize import segment_words
from text_mate_backend.readability.types import (
    BandConfig,
    ImpactLevel,
    LanguageCode,
    ReadabilityBand,
    ReferenceRow,
    ScaleInfo,
)

#: ZIX raises ``ValueError`` above this length (spaCy's ``max_length``).
MAX_ZIX_CHARS = 1_000_000

#: ZIX warns that the estimate is unreliable *at or below* five words, so the
#: floor for scoring is six. (docs/simplify_redesign.md section 4.2 says 5,
#: taken from blokkli's WSTF config; ZIX's own warning is the better authority
#: and the eval harness independently landed on 6.)
MIN_WORDS = 6

#: ZIX is clipped to this range.
SCALE_MIN = -10.0
SCALE_MAX = 10.0

#: easy <=> ZIX >= 0 <=> CEFR A1/A2/B1; ok down to -2 (B2); hard below that.
#: The impact thresholds follow the CEFR boundaries of ``zix.get_cefr``.
BAND_CONFIG = BandConfig(
    direction="higher_easier",
    easy=0.0,
    ok=-2.0,
    impact_thresholds=(0.0, -2.0, -4.0),
)

REFERENCE_TABLE: tuple[ReferenceRow, ...] = (
    ReferenceRow("ZIX 4 bis 10", "A1 — sehr leicht"),
    ReferenceRow("ZIX 2 bis 4", "A2 — leicht (Zielbereich)"),
    ReferenceRow("ZIX 0 bis 2", "B1 — leicht (Zielbereich)"),
    ReferenceRow("ZIX -2 bis 0", "B2 — mittelschwer (sollte einfacher werden)"),
    ReferenceRow("ZIX -4 bis -2", "C1 — schwer — wird beanstandet"),
    ReferenceRow("ZIX -10 bis -4", "C2 — sehr schwer — muss vereinfacht werden"),
)


def _zix_score(text: str) -> float | None:
    """Call ZIX, swallowing its short-text warnings.

    Imported lazily: importing ``zix.understandability`` loads spaCy, a German
    language model and two pickled sklearn models.
    """
    from zix.understandability import get_zix

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        score: float | None = get_zix(text)
    return score


def _zix_cefr(score: float) -> str:
    """Map a ZIX score to a CEFR level using ZIX's own thresholds."""
    from zix.understandability import get_cefr

    level: str = get_cefr(score)
    return level


@final
class GermanAnalyzer:
    """ZIX-backed readability analyzer for German."""

    language: LanguageCode = "de"
    score_label: str = "ZIX"
    min_words: int = MIN_WORDS

    def score(self, text: str) -> float | None:
        """Score German text with ZIX, or None when it cannot be scored.

        Returns None instead of raising for over-long input: ZIX raises
        ``ValueError`` above 1,000,000 characters, which used to reach the
        client as a 500.
        """
        stripped = text.strip()
        if not stripped or len(stripped) > MAX_ZIX_CHARS:
            return None
        if len(segment_words(stripped)) < self.min_words:
            return None

        raw = _zix_score(stripped)
        return round_score(raw) if raw is not None else None

    def band(self, score: float) -> ReadabilityBand:
        return classify_band(score, BAND_CONFIG)

    def impact(self, score: float) -> ImpactLevel:
        return impact_for_score(score, BAND_CONFIG)

    def cefr(self, score: float) -> str | None:
        return _zix_cefr(score)

    def format_score(self, score: float) -> str:
        return f"{_zix_cefr(score)} (ZIX {score:.1f})"

    def agent_context(self) -> str:
        return build_agent_context(self.score_label, REFERENCE_TABLE)

    def reference_table(self) -> Sequence[ReferenceRow]:
        return REFERENCE_TABLE

    def scale_info(self) -> ScaleInfo:
        """ZIX has a fixed [-10, 10] range, so the generic padding is overridden."""
        generic = build_scale_info(BAND_CONFIG)
        return ScaleInfo(
            thresholds=generic.thresholds,
            direction=generic.direction,
            scale_min=SCALE_MIN,
            scale_max=SCALE_MAX,
        )
