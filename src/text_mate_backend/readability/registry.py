"""Language -> analyzer lookup.

An unsupported language returns **None**, never a fallback analyzer: scoring
non-German text with ZIX (or any other language's calibration) would produce a
number that looks authoritative and means nothing. The caller is expected to
skip scoring entirely in that case.
"""

from typing import get_args

from text_mate_backend.readability.languages.english import EnglishAnalyzer
from text_mate_backend.readability.languages.french import FrenchAnalyzer
from text_mate_backend.readability.languages.german import GermanAnalyzer
from text_mate_backend.readability.languages.italian import ItalianAnalyzer
from text_mate_backend.readability.types import SUPPORTED_LANGUAGES, LanguageCode, ReadabilityAnalyzer

_ANALYZERS: dict[LanguageCode, ReadabilityAnalyzer] = {
    "de": GermanAnalyzer(),
    "en": EnglishAnalyzer(),
    "fr": FrenchAnalyzer(),
    "it": ItalianAnalyzer(),
}


def get_analyzer(language: str | None) -> ReadabilityAnalyzer | None:
    """Return the analyzer for ``language``, or None when it is unsupported.

    >>> get_analyzer("de").score_label
    'ZIX'
    >>> get_analyzer("es") is None
    True
    >>> get_analyzer(None) is None
    True
    """
    if language is None:
        return None
    normalized = language.lower().strip()
    if normalized not in SUPPORTED_LANGUAGES:
        return None
    # `normalized` is narrowed to LanguageCode by the membership test above.
    return _ANALYZERS[normalized]


def is_supported(language: str | None) -> bool:
    """Whether a language has an analyzer.

    >>> is_supported("fr"), is_supported("es")
    (True, False)
    """
    return get_analyzer(language) is not None


def supported_languages() -> tuple[LanguageCode, ...]:
    """All languages with an analyzer.

    >>> supported_languages()
    ('de', 'en', 'fr', 'it')
    """
    return SUPPORTED_LANGUAGES


# Guard against SUPPORTED_LANGUAGES and the registry drifting apart.
assert set(_ANALYZERS) == set(get_args(LanguageCode)), "registry does not cover every LanguageCode"
