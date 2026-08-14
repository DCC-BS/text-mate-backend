"""Language-agnostic tokenization.

Port of the tokenization helpers in ``blokkli/editor``
(``src/modules/readability/runtime/analyzers/builtin.ts``, MIT), which in turn
mirror ``@lunarisapp/language``: keep letters, numbers, whitespace and
apostrophes (for contractions), lowercase, split on whitespace runs.

The JavaScript originals use ``\\p{L}``/``\\p{N}`` character classes. Python's
``re`` has no ``\\p{...}`` support, but ``\\w`` is documented as "alphanumeric
characters (as defined by ``str.isalnum()``) as well as the underscore", i.e.
exactly ``\\p{L} | \\p{N} | _`` — so the underscore is stripped separately to
make the two implementations agree.
"""

import re
from collections.abc import Callable

#: Everything that is not a letter, number, whitespace or apostrophe.
_NON_WORD_RE = re.compile(r"[^\w\s']")
_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_RE = re.compile(r"[^.!?。！？\n\r]+[.!?。！？]*[\n\r]*")
#: Word-like segments, used only for the min-words gate. Approximates
#: ``Intl.Segmenter(granularity: "word")`` with ``isWordLike``, which counts
#: numbers as words too.
_WORD_LIKE_RE = re.compile(r"[^\W_]+(?:'[^\W_]+)?")

#: Words longer than this are "long words" (LIX and friends).
LONG_WORD_THRESHOLD = 6


def get_words(text: str) -> list[str]:
    """Split text into lowercased words.

    >>> get_words("The quick, brown fox — don't stop!")
    ['the', 'quick', 'brown', 'fox', "don't", 'stop']
    """
    cleaned = _NON_WORD_RE.sub("", text).replace("_", "").lower()
    return [word for word in _WHITESPACE_RE.split(cleaned) if word]


def get_sentences(text: str) -> list[str]:
    """Split text into sentence-ish chunks.

    >>> get_sentences("One. Two! Three?")
    ['One.', ' Two!', ' Three?']
    """
    return _SENTENCE_RE.findall(text)


def sentence_count(text: str) -> int:
    """Count sentences, ignoring fragments of two words or fewer. Never below 1.

    >>> sentence_count("The cat sat on the mat. The dog ran away. Ok.")
    2
    """
    sentences = get_sentences(text)
    ignored = sum(1 for sentence in sentences if len(get_words(sentence)) <= 2)
    return max(1, len(sentences) - ignored)


def word_count(text: str) -> int:
    """Number of words.

    >>> word_count("The cat sat on the mat.")
    6
    """
    return len(get_words(text))


def long_word_count(text: str, threshold: int = LONG_WORD_THRESHOLD) -> int:
    """Number of words longer than ``threshold`` characters.

    >>> long_word_count("Die komplexen Vorschriften sind lang.")
    2
    """
    return sum(1 for word in get_words(text) if len(word) > threshold)


def char_count(text: str) -> int:
    """Number of non-whitespace characters, punctuation included.

    >>> char_count("ab cd\\nef")
    6
    """
    return len(_WHITESPACE_RE.sub("", text))


def avg_sentence_length(text: str) -> float:
    """Mean number of words per sentence.

    >>> avg_sentence_length("The cat sat on the mat. The dog ran to the park.")
    6.0
    """
    sentences = sentence_count(text)
    return word_count(text) / sentences if sentences else 0.0


def avg_words_per_sentence(text: str) -> float:
    """Alias of :func:`avg_sentence_length`, kept for formula readability."""
    return avg_sentence_length(text)


def avg_syllables_per_word(text: str, syllable_count: Callable[[str], int]) -> float:
    """Mean number of syllables per word, 0.0 for a text without words."""
    words = get_words(text)
    if not words:
        return 0.0
    return sum(syllable_count(word) for word in words) / len(words)


def polysyllable_count(text: str, syllable_count: Callable[[str], int]) -> int:
    """Number of words with more than two syllables."""
    return sum(1 for word in get_words(text) if syllable_count(word) > 2)


def segment_words(text: str) -> list[str]:
    """Word-like segments used for the min-words confidence gate.

    >>> segment_words("Too short.")
    ['Too', 'short']
    """
    return _WORD_LIKE_RE.findall(text)
