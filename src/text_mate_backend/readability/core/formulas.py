"""Pure readability formulas.

Copied verbatim (modulo language) from ``blokkli/editor``
(``src/modules/readability/runtime/analyzers/builtin.ts``, MIT), which copied
them from ``@lunarisapp/readability`` (MIT). See the ``NOTICE`` file.

Wiener Sachtextformel is deliberately *not* ported: German is scored with ZIX,
which has vocabulary difficulty in its feature set, so WSTF would be dead code.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

_GULPEASE_BASE = 89.0
_GULPEASE_SENTENCES_COEF = 300.0
_GULPEASE_CHARS_COEF = 10.0


@dataclass(frozen=True, slots=True)
class FleschCoefficients:
    """Language-specific Flesch Reading Ease coefficients."""

    base: float
    sentences: float
    syllables_per_word: float


def flesch_reading_ease(
    sentences: float,
    syllables_per_word: float,
    coefficients: FleschCoefficients,
) -> float:
    """Flesch Reading Ease. ``sentences`` is the mean sentence length in words.

    >>> round(flesch_reading_ease(6.0, 1.2, FleschCoefficients(206.835, 1.015, 84.6)), 1)
    99.2
    """
    return coefficients.base - coefficients.sentences * sentences - coefficients.syllables_per_word * syllables_per_word


def gulpease_index(sentences: float, chars: float, words: float) -> float:
    """Gulpease index (Italian). Higher is easier.

    >>> gulpease_index(2, 100, 20)
    69.0
    """
    return (_GULPEASE_SENTENCES_COEF * sentences - _GULPEASE_CHARS_COEF * chars) / words + _GULPEASE_BASE


def lix(words: float, long_words: float, words_per_sentence: float) -> float:
    """LIX (Läsbarhetsindex). Higher is harder.

    >>> lix(20, 5, 10.0)
    35.0
    """
    if words == 0:
        return 0.0
    return words_per_sentence + (long_words * 100.0) / words


def safe_score(compute: Callable[[], float]) -> float | None:
    """Run ``compute``, returning None instead of a non-finite value or an error.

    Mirrors blokkli's ``safe()``, where division by zero yields ``Infinity``
    rather than raising.

    >>> safe_score(lambda: 1 / 0)
    """
    try:
        value = compute()
    except (ArithmeticError, ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def round_score(value: float) -> float:
    """Round to one decimal the way JavaScript's ``Math.round(n * 10) / 10`` does.

    Half-way values go up (towards +Infinity), unlike Python's banker's rounding.

    >>> round_score(2.25), round_score(-2.25), round_score(2.349)
    (2.3, -2.2, 2.3)
    """
    return math.floor(value * 10.0 + 0.5) / 10.0
