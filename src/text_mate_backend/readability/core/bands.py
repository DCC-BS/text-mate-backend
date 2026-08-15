"""Band classification, impact severity and score assembly.

Port of ``classifyBandGeneric`` / ``impactForScoreGeneric`` /
``buildAgentContext`` / ``getScaleInfo`` from ``blokkli/editor``
(``src/modules/readability/runtime/analyzers/builtin.ts``, MIT). All of it is
driven by a :class:`BandConfig`, so both score directions are handled by the
same code.
"""

import math
from collections.abc import Sequence

from text_mate_backend.readability.types import (
    BandConfig,
    ImpactLevel,
    ReadabilityAnalyzer,
    ReadabilityBand,
    ReadabilityScore,
    ReferenceRow,
    ScaleInfo,
)

#: A text is "in target" exactly when it reaches the easy band.
TARGET_BAND: ReadabilityBand = "easy"


def classify_band(score: float, config: BandConfig) -> ReadabilityBand:
    """Classify a raw score into easy / ok / hard.

    >>> config = BandConfig(direction="higher_easier", easy=60, ok=50, impact_thresholds=(40, 25, 10))
    >>> classify_band(75, config), classify_band(55, config), classify_band(45, config)
    ('easy', 'ok', 'hard')
    """
    if config.direction == "higher_easier":
        if score >= config.easy:
            return "easy"
        if score >= config.ok:
            return "ok"
        return "hard"

    if score <= config.easy:
        return "easy"
    if score <= config.ok:
        return "ok"
    return "hard"


def impact_for_score(score: float, config: BandConfig) -> ImpactLevel:
    """Severity of a raw score, from the config's ``(moderate, serious, critical)``.

    >>> config = BandConfig(direction="higher_easier", easy=60, ok=50, impact_thresholds=(40, 25, 10))
    >>> impact_for_score(5, config), impact_for_score(20, config), impact_for_score(65, config)
    ('critical', 'serious', 'minor')
    """
    moderate, serious, critical = config.impact_thresholds
    if config.direction == "higher_easier":
        if score < critical:
            return "critical"
        if score < serious:
            return "serious"
        if score < moderate:
            return "moderate"
        return "minor"

    if score >= critical:
        return "critical"
    if score >= serious:
        return "serious"
    if score >= moderate:
        return "moderate"
    return "minor"


def in_target(score: float, config: BandConfig) -> bool:
    """Whether a score reaches the simplification target."""
    return classify_band(score, config) == TARGET_BAND


def build_agent_context(label: str, rows: Sequence[ReferenceRow]) -> str:
    """Render a score reference table for the rewrite prompt."""
    body = "\n".join(f"- {row.range_label}: {row.label}" for row in rows)
    return f"## {label} Score Reference\n\n{body}"


def build_scale_info(config: BandConfig) -> ScaleInfo:
    """Visual range around the band edges, padded by half their distance.

    >>> build_scale_info(BandConfig("higher_easier", 60.0, 50.0, (40.0, 25.0, 10.0)))
    ScaleInfo(thresholds=(50.0, 60.0), direction='higher_easier', scale_min=45.0, scale_max=65.0)
    """
    lower = min(config.easy, config.ok)
    upper = max(config.easy, config.ok)
    # blokkli rounds the padding to a whole number (Math.round).
    padding = math.floor((upper - lower) * 0.5 + 0.5)
    return ScaleInfo(
        thresholds=(lower, upper),
        direction=config.direction,
        scale_min=max(0.0, lower - padding),
        scale_max=upper + padding,
    )


def build_score(analyzer: ReadabilityAnalyzer, value: float) -> ReadabilityScore:
    """Assemble the full :class:`ReadabilityScore` for a raw metric value."""
    band = analyzer.band(value)
    return ReadabilityScore(
        language=analyzer.language,
        score=value,
        score_label=analyzer.score_label,
        band=band,
        impact=analyzer.impact(value),
        cefr=analyzer.cefr(value),
        in_target=band == TARGET_BAND,
        formatted=analyzer.format_score(value),
    )
