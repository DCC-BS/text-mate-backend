"""Paragraph chunking for the simplify pipeline.

Splits plain text on blank lines into indexed units that keep their offsets in
the original string, classifies each as heading / list item / paragraph,
merges consecutive paragraphs into gate-sized blocks, and reassembles
rewritten units back into a document.

Rules that drive the design:

* only ``paragraph`` units are rewritten -- headings and list items pass
  through verbatim, because rewriting them destroys document structure;
* a unit with fewer words than the analyzer's ``min_words`` is *unscorable* and
  also passes through: a rewrite that cannot be verified must not be made;
* the readability gate never runs on a raw, blank-line-delimited paragraph --
  :func:`merge_units` combines consecutive ``paragraph`` units forward until
  each block has at least ``min_unit_words`` words, because ZIX measured on a
  corpus-median 35-word paragraph deviates from the full-text score by ~1.8, a
  band and a half; see ``docs/simplify_redesign.md`` section 2 for the
  measurement rationale. Headings and list items are barriers: merging never crosses
  them and never combines them with a neighbouring paragraph.

Reassembly is 1-in-N-out: a unit's replacement may itself contain blank lines,
because splitting one dense paragraph into several is the single most effective
simplification move.

Deliberately simplify-local for now. The advisor's only splitter today is
``services/advisor.py`` ``_split_into_search_units`` (sentence-level,
offset-preserving, built for fuzzy source matching); the paragraph windowing
both features want is specified in ``docs/advisor_redesign.md`` section 4.2.3
but unbuilt. Unify in future advisor updates (see ``docs/simplify_redesign.md``
section 2).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from text_mate_backend.readability.core.tokenize import segment_words
from text_mate_backend.readability.languages.german import MIN_WORDS as GERMAN_MIN_WORDS

#: What a unit is, which decides whether it may be rewritten.
UnitKind = Literal["heading", "list_item", "paragraph"]

#: Units are separated by a blank line (whitespace-only lines count).
_UNIT_SEPARATOR_RE = re.compile(r"\r?\n[ \t]*\r?\n")

#: Bullet or enumeration markers at the start of a line.
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•·–—+]|\(?[0-9]{1,3}[.)]|\(?[a-zA-Z][.)])\s+")

#: Markdown-style heading marker.
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")

#: A single line no longer than this, without terminal punctuation, is a heading.
HEADING_MAX_CHARS = 90
HEADING_MAX_WORDS = 12

#: Sentence-terminating punctuation; a line ending in one of these is prose.
_TERMINAL_PUNCTUATION = ".!?:;"

#: Fallback when no analyzer-specific minimum is supplied: German is the corpus
#: language, so its analyzer's floor is the sensible default.
DEFAULT_MIN_WORDS = GERMAN_MIN_WORDS

#: Units are joined back together with a blank line.
UNIT_JOINER = "\n\n"

#: Merge target for :func:`merge_units` (``simplify_min_unit_words``, section 14.2 /
#: 14.5). 100 gives ~2:1 merging on the real corpus (two typical paragraphs per unit)
#: while landing where the ZIX prefix/full deviation is well under half a 2-point band.
DEFAULT_MIN_UNIT_WORDS = 100


@dataclass(frozen=True, slots=True)
class TextUnit:
    """One blank-line-delimited unit of a document."""

    index: int
    text: str
    start: int
    end: int
    kind: UnitKind
    word_count: int
    unscorable: bool

    @property
    def rewritable(self) -> bool:
        """Whether the simplifier may rewrite this unit."""
        return self.kind == "paragraph" and not self.unscorable


def classify_unit(text: str) -> UnitKind:
    """Classify a single unit.

    >>> classify_unit("Anmeldung zur Prüfung")
    'heading'
    >>> classify_unit("- Sie brauchen einen Ausweis")
    'list_item'
    >>> classify_unit("Sie müssen sich bis zum 1. Mai anmelden.")
    'paragraph'
    """
    stripped = text.strip()
    if not stripped:
        return "paragraph"

    if _MARKDOWN_HEADING_RE.match(stripped):
        return "heading"

    lines = [line for line in stripped.splitlines() if line.strip()]
    if any(_LIST_MARKER_RE.match(line) for line in lines):
        return "list_item"

    is_single_line = len(lines) == 1
    if (
        is_single_line
        and len(stripped) <= HEADING_MAX_CHARS
        and len(segment_words(stripped)) <= HEADING_MAX_WORDS
        and stripped[-1] not in _TERMINAL_PUNCTUATION
    ):
        return "heading"

    return "paragraph"


def split_units(text: str, min_words: int = DEFAULT_MIN_WORDS) -> list[TextUnit]:
    """Split ``text`` on blank lines into classified, offset-preserving units.

    ``min_words`` should come from the active analyzer; units below it are
    marked ``unscorable`` and are passed through unchanged.

    >>> units = split_units("Titel\\n\\nEin ausreichend langer Satz mit genug Wörtern darin.")
    >>> [(u.index, u.kind, u.rewritable) for u in units]
    [(0, 'heading', False), (1, 'paragraph', True)]
    >>> units[1].text == "Ein ausreichend langer Satz mit genug Wörtern darin."
    True
    """
    units: list[TextUnit] = []
    for index, (block, start) in enumerate(_iter_blocks(text)):
        word_count = len(segment_words(block))
        units.append(
            TextUnit(
                index=index,
                text=block,
                start=start,
                end=start + len(block),
                kind=classify_unit(block),
                word_count=word_count,
                unscorable=word_count < min_words,
            )
        )
    return units


def rewritable_units(units: Sequence[TextUnit]) -> list[TextUnit]:
    """The units the simplifier is allowed to rewrite, in document order."""
    return [unit for unit in units if unit.rewritable]


def merge_units(
    units: Sequence[TextUnit],
    min_unit_words: int = DEFAULT_MIN_UNIT_WORDS,
    min_words: int = DEFAULT_MIN_WORDS,
) -> list[TextUnit]:
    """Merge consecutive ``paragraph`` units forward until each has >= ``min_unit_words``.

    This is the section 14.2 gate-sizing step: the readability analyzer is too noisy at
    raw-paragraph length to gate on directly, so paragraphs are combined into blocks
    before scoring. Headings and list items are **barriers** -- merging never crosses
    them, and they are never merged with anything themselves. The trailing block of a
    run may end up short of ``min_unit_words`` when the document (or the span before the
    next barrier) simply runs out of paragraphs; it is still returned as its own unit,
    marked ``unscorable`` only if it falls under the analyzer's own ``min_words`` floor.

    Units are re-indexed ``0..n-1`` in document order; a merged unit's ``start``/``end``
    span its first and last source unit, and its ``text`` is those units' text rejoined
    with :data:`UNIT_JOINER`, matching how :func:`reassemble` already joins output.

    >>> units = split_units(
    ...     "Erster kurzer Satz.\\n\\nZweiter kurzer Satz.\\n\\n- Ein Listenpunkt\\n\\n"
    ...     "Dritter kurzer Satz."
    ... )
    >>> merged = merge_units(units, min_unit_words=5)
    >>> [(u.index, u.kind, u.word_count) for u in merged]
    [(0, 'paragraph', 6), (1, 'list_item', 2), (2, 'paragraph', 3)]
    """
    merged: list[TextUnit] = []
    buffer: list[TextUnit] = []
    buffer_words = 0

    def flush() -> None:
        nonlocal buffer, buffer_words
        if not buffer:
            return
        merged.append(
            TextUnit(
                index=len(merged),
                text=UNIT_JOINER.join(unit.text for unit in buffer),
                start=buffer[0].start,
                end=buffer[-1].end,
                kind="paragraph",
                word_count=buffer_words,
                unscorable=buffer_words < min_words,
            )
        )
        buffer = []
        buffer_words = 0

    for unit in units:
        if unit.kind != "paragraph":
            flush()
            merged.append(
                TextUnit(
                    index=len(merged),
                    text=unit.text,
                    start=unit.start,
                    end=unit.end,
                    kind=unit.kind,
                    word_count=unit.word_count,
                    unscorable=unit.unscorable,
                )
            )
            continue

        buffer.append(unit)
        buffer_words += unit.word_count
        if buffer_words >= min_unit_words:
            flush()

    flush()
    return merged


def reassemble(units: Sequence[TextUnit], replacements: Mapping[int, str]) -> str:
    """Join units back into a document, substituting rewritten ones by index.

    Units keep their original order; a replacement may contain blank lines of
    its own (one unit in, several paragraphs out).

    >>> units = split_units("Ein langer Satz mit vielen Wörtern darin.\\n\\nNoch ein Satz mit Wörtern.")
    >>> reassemble(units, {0: "Kurz.\\n\\nUnd kurz."})
    'Kurz.\\n\\nUnd kurz.\\n\\nNoch ein Satz mit Wörtern.'
    """
    return reassemble_with_spans(units, replacements)[0]


def reassemble_with_spans(
    units: Sequence[TextUnit], replacements: Mapping[int, str]
) -> tuple[str, dict[int, tuple[int, int]]]:
    """Like :func:`reassemble`, but also report each unit's span in the assembled text.

    ``TextUnit.start``/``end`` are offsets into the *source*; they are the wrong
    coordinate space once a unit's rewrite has shipped, because a rewrite is rarely
    the same length as what it replaced (one unit in, N paragraphs out -- the same
    fact that makes ``UNIT_JOINER``-based reassembly 1-in-N-out in the first place).
    This walks the output exactly as it is built, so a unit that passed through
    unchanged and one whose rewrite changed length are both tracked correctly, in
    Python code points (the caller converts to UTF-16 code units at the API boundary,
    see ``SimplifyDoneEvent.unconverged_ranges``).

    Spans are half-open ``[start, end)`` and keyed by ``unit.index`` -- the same index
    space ``reassemble`` substitutes ``replacements`` by.

    >>> units = split_units("Ein langer Satz mit vielen Wörtern darin.\\n\\nNoch ein Satz mit Wörtern.")
    >>> text, spans = reassemble_with_spans(units, {0: "Kurz.\\n\\nUnd kurz."})
    >>> text[spans[0][0] : spans[0][1]]
    'Kurz.\\n\\nUnd kurz.'
    >>> text[spans[1][0] : spans[1][1]]
    'Noch ein Satz mit Wörtern.'
    """
    ordered = sorted(units, key=lambda unit: unit.index)
    parts: list[str] = []
    spans: dict[int, tuple[int, int]] = {}
    position = 0
    for position_in_order, unit in enumerate(ordered):
        if position_in_order > 0:
            position += len(UNIT_JOINER)
        piece = replacements.get(unit.index, unit.text).strip()
        start = position
        end = start + len(piece)
        spans[unit.index] = (start, end)
        parts.append(piece)
        position = end
    return UNIT_JOINER.join(parts), spans


def _iter_blocks(text: str) -> list[tuple[str, int]]:
    """Yield ``(stripped block, offset in the original text)`` pairs."""
    blocks: list[tuple[str, int]] = []
    position = 0
    for separator in _UNIT_SEPARATOR_RE.finditer(text):
        blocks.append((text[position : separator.start()], position))
        position = separator.end()
    blocks.append((text[position:], position))

    result: list[tuple[str, int]] = []
    for raw, offset in blocks:
        stripped = raw.strip()
        if not stripped:
            continue
        leading_whitespace = len(raw) - len(raw.lstrip())
        result.append((stripped, offset + leading_whitespace))
    return result
