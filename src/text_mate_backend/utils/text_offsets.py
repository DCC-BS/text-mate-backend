"""Translation between Python and JavaScript string indexing.

Every offset this backend sends to a client crosses an indexing-scheme boundary,
and the two schemes agree often enough that getting it wrong passes almost every
test anyone thinks to write. Hence one implementation, shared by every feature
that reports ranges: the advisor's ``ViolationRange`` and the simplifier's
``UnconvergedRange``.
"""


def to_utf16_offset(text: str, codepoint_offset: int) -> int:
    """Translate a Python code-point index into a JavaScript UTF-16 code-unit index.

    Python ``str`` is a sequence of Unicode code points, so ``str.find``, slicing
    and regex offsets are code-point based. JavaScript stores strings as UTF-16
    and indexes them by **code unit**. The two agree for every Basic Multilingual
    Plane character — all of Latin, umlauts, ``ß``, accented letters, Cyrillic,
    CJK — and diverge only above U+FFFF (emoji, some symbols, historic scripts),
    which are one Python code point but two UTF-16 code units (a surrogate pair).

    That is exactly what makes this worth centralising: German administrative
    prose is entirely BMP, so a code-point offset shipped as-is is correct until
    the first emoji, and then every subsequent range on that document silently
    shifts.

    Translate at the API boundary only; all internal resolution logic works on
    code points.

    >>> to_utf16_offset("Grüße", 5)
    5
    >>> to_utf16_offset("a🎉b", 3)
    4
    """
    return sum(2 if ord(ch) >= 0x10000 else 1 for ch in text[:codepoint_offset])
