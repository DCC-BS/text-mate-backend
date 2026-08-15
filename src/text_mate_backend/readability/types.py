"""Shared types for the language-aware readability module.

The vocabulary mirrors ``blokkli/editor``'s readability analyzer contract
(``src/runtime/editor/features/analyze/readability/types.ts``, MIT) so that the
ported formulas, bands and impact thresholds keep their original semantics.
See the ``NOTICE`` file for attribution.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

#: Languages for which a readability analyzer exists. Everything else is
#: deliberately unsupported: the caller then skips scoring instead of scoring
#: with an inappropriate metric.
LanguageCode = Literal["de", "en", "fr", "it"]

SUPPORTED_LANGUAGES: tuple[LanguageCode, ...] = ("de", "en", "fr", "it")

#: Classification of a score. ``easy`` is the simplification target.
ReadabilityBand = Literal["easy", "ok", "hard"]

#: Severity of a text that is outside the target band.
ImpactLevel = Literal["minor", "moderate", "serious", "critical"]

#: Whether a higher raw score means an easier or a harder text.
ScoreDirection = Literal["higher_easier", "higher_harder"]


@dataclass(frozen=True, slots=True)
class ReferenceRow:
    """One row of an analyzer's score reference table (rendered into prompts)."""

    range_label: str
    label: str


@dataclass(frozen=True, slots=True)
class BandConfig:
    """Calibration of a single metric: band edges plus impact thresholds.

    ``easy`` and ``ok`` are the band edges, interpreted according to
    ``direction``. ``impact_thresholds`` is ``(moderate, serious, critical)`` in
    the same order blokkli uses.
    """

    direction: ScoreDirection
    easy: float
    ok: float
    impact_thresholds: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class ScaleInfo:
    """Visual range of a score bar. ``thresholds`` is ascending (lower first)."""

    thresholds: tuple[float, float]
    direction: ScoreDirection
    scale_min: float
    scale_max: float


class ReadabilityScore(BaseModel):
    """A scored text: the raw value plus everything derived from it."""

    language: LanguageCode = Field(description="Language the text was scored in")
    score: float = Field(description="Raw metric value, rounded to one decimal")
    score_label: str = Field(description='Short name of the metric ("ZIX", "CEFR", "LIX", "Gulpease")')
    band: ReadabilityBand = Field(description="Calibrated band of the score")
    impact: ImpactLevel = Field(description="Severity of the readability problem")
    cefr: str | None = Field(
        default=None, description="CEFR level (A1-C2) where the metric supports it; None for fr/it"
    )
    in_target: bool = Field(description="True when the text is in the target band (band == easy)")
    formatted: str = Field(description="Human-readable rendering of the score")


@runtime_checkable
class ReadabilityAnalyzer(Protocol):
    """Contract every language analyzer implements.

    Analyzers are stateless and cheap to construct; the language is baked in
    rather than passed per call (blokkli passes a langcode because a single
    analyzer object serves all languages there).
    """

    language: LanguageCode
    score_label: str
    min_words: int

    def score(self, text: str) -> float | None:
        """Return the raw metric value, or None when the text cannot be scored."""
        ...

    def band(self, score: float) -> ReadabilityBand:
        """Classify a raw score into easy / ok / hard."""
        ...

    def impact(self, score: float) -> ImpactLevel:
        """Severity of a raw score."""
        ...

    def cefr(self, score: float) -> str | None:
        """CEFR level for a raw score, or None when the metric has no mapping."""
        ...

    def format_score(self, score: float) -> str:
        """Human-readable rendering of a raw score."""
        ...

    def agent_context(self) -> str:
        """Score reference table for the rewrite prompt."""
        ...

    def reference_table(self) -> Sequence[ReferenceRow]:
        """Rows of the score reference table."""
        ...

    def scale_info(self) -> ScaleInfo:
        """Visual range for rendering the score."""
        ...
