"""Language-aware readability scoring.

Public API::

    language = detect_language(text)          # None when unsupported/unclear
    analyzer = get_analyzer(language)          # None when unsupported
    if analyzer is not None:
        value = analyzer.score(text)           # None when not scorable
        result = build_score(analyzer, value)  # band, impact, CEFR, in_target

Language-agnostic mechanics (tokenization, formulas, band classification) live
in :mod:`~text_mate_backend.readability.core`; per-language calibration lives in
:mod:`~text_mate_backend.readability.languages`.

Formulas, bands and impact thresholds for en/fr/it are ported from
``blokkli/editor`` (MIT), which took them from ``@lunarisapp/readability``
(MIT); German uses ZIX instead. See the ``NOTICE`` file for attribution and
``docs/simplify_redesign.md`` section 4.2 for the design.
"""

from text_mate_backend.readability.core.bands import (
    TARGET_BAND,
    build_agent_context,
    build_score,
    classify_band,
    impact_for_score,
    in_target,
)
from text_mate_backend.readability.detection import (
    MIN_CONFIDENCE,
    MIN_DETECTION_CHARS,
    detect_language,
    detect_raw_language,
)
from text_mate_backend.readability.registry import get_analyzer, is_supported, supported_languages
from text_mate_backend.readability.types import (
    SUPPORTED_LANGUAGES,
    BandConfig,
    ImpactLevel,
    LanguageCode,
    ReadabilityAnalyzer,
    ReadabilityBand,
    ReadabilityScore,
    ReferenceRow,
    ScaleInfo,
    ScoreDirection,
)

__all__ = [
    "MIN_CONFIDENCE",
    "MIN_DETECTION_CHARS",
    "SUPPORTED_LANGUAGES",
    "TARGET_BAND",
    "BandConfig",
    "ImpactLevel",
    "LanguageCode",
    "ReadabilityAnalyzer",
    "ReadabilityBand",
    "ReadabilityScore",
    "ReferenceRow",
    "ScaleInfo",
    "ScoreDirection",
    "build_agent_context",
    "build_score",
    "classify_band",
    "detect_language",
    "detect_raw_language",
    "get_analyzer",
    "impact_for_score",
    "in_target",
    "is_supported",
    "supported_languages",
]
