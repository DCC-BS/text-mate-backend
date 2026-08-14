"""Composable building blocks for the simplification rewrite prompt.

Implements ``docs/simplify_redesign.md`` §5.3 (German) and §5.4 (everything else). The
prompt is assembled from small, independently testable renderers rather than one giant
f-string, so that the readability loop can add exactly the blocks it has data for:

============================  =========================================================
Block                         Renderer
============================  =========================================================
Score reference               :func:`render_score_reference_block`
Per-paragraph issue list      :func:`render_issue_list`
Retry (previous attempt,      :func:`render_retry_block`
missing facts, escalation)
Passing exemplars             :func:`render_passing_examples`
CHUNKED neighbour context     :func:`render_neighbour_context`
Whole prompt                  :func:`build_rewrite_prompt`
============================  =========================================================

The retry and exemplar blocks follow blokkli's ``fixReadability`` stream template
(``retryFields`` / ``passingFields``, MIT), including its truncation limits and its
"try a different approach" escalation.

Every renderer takes **plain data** — floats, strings, and the small frozen dataclasses
defined here — never a service, analyzer or agent object. That keeps the prompt buildable
(and testable) before the loop, the readability module or the scoring service exist.

Language selection is a single switch: ``de`` gets ``SIMPLIFY_STYLE_DE`` plus
``REWRITE_COMPLETE`` and German section headings; every other language code gets
``GENERIC_SIMPLIFY_INSTRUCTIONS`` and English section headings
(see :func:`select_rules`).
"""
# ruff: noqa: E501  # Line too long - German language rules and prompts need to be preserved exactly

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from text_mate_backend.utils.easy_language import REWRITE_COMPLETE, SYSTEM_MESSAGE_ES
from text_mate_backend.utils.simplify_generic import GENERIC_SIMPLIFY_INSTRUCTIONS, GENERIC_SYSTEM_MESSAGE
from text_mate_backend.utils.simplify_style import SIMPLIFY_STYLE_DE

GERMAN: str = "de"
"""The one language for which an authored, reviewed rule set exists."""

MAX_ORIGINAL_CHARS: int = 500
"""Truncation limit for quoted originals and previous attempts (blokkli: 500)."""

MAX_EXAMPLE_CHARS: int = 200
"""Truncation limit for quoted passing exemplars (blokkli: 200)."""


# =============================================================================
# DATA
# =============================================================================


@dataclass(frozen=True)
class ScoreReference:
    """The active analyzer's score, band and reference table, as plain values.

    ``reference_table`` is whatever the analyzer's ``agent_context()`` returns; it is
    inserted verbatim, so it must already be written in the text's language.
    """

    label: str
    score: float | None = None
    band: str | None = None
    cefr: str | None = None
    scale: str | None = None
    target: str | None = None
    reference_table: str | None = None


@dataclass(frozen=True)
class ParagraphIssue:
    """One paragraph that is still outside the target band."""

    index: int
    text: str
    score: float | None = None
    band: str | None = None
    impact: str | None = None


@dataclass(frozen=True)
class PassingExample:
    """A paragraph from the same document that already reached the target band."""

    index: int
    text: str
    score: float | None = None


@dataclass(frozen=True)
class PreviousAttempt:
    """The previous rewrite, its score, and the facts the fidelity gate found missing."""

    attempt: int
    text: str
    score: float | None = None
    band: str | None = None
    missing_facts: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class NeighbourContext:
    """Read-only surroundings of the target paragraph in CHUNKED mode."""

    previous_text: str | None = None
    following_text: str | None = None
    document_summary: str | None = None


@dataclass(frozen=True)
class _Labels:
    """Section headings and fixed sentences for one language branch."""

    scoring_intro: str
    current_score: str
    target: str
    issues_intro: str
    issue_item: str
    retry_heading: str
    retry_intro: str
    retry_previous: str
    retry_score: str
    retry_missing: str
    retry_escalation_intro: str
    examples_intro: str
    context_summary: str
    context_previous: str
    context_following: str
    context_only_target: str
    prompt_intro: str
    prompt_rules_intro: str
    prompt_outro: str


_LABELS_DE = _Labels(
    scoring_intro="Der Text wird automatisch auf Verständlichkeit bewertet ({label}).",
    current_score="Aktuell: {current}.",
    target="Ziel: {target}.",
    issues_intro="Diese Absätze sind noch zu schwer verständlich:",
    issue_item="- Absatz {index}: «{text}»{meta}",
    retry_heading="Vorheriger Versuch",
    retry_intro="Dein Versuch {attempt} hat das Ziel noch nicht erreicht.",
    retry_previous="Deine vorherige Fassung:",
    retry_score="Bewertung deiner vorherigen Fassung: {current}.",
    retry_missing="Diese Informationen aus dem Originaltext haben in deiner vorherigen Fassung gefehlt. Sie müssen diesmal vollständig vorkommen:",
    retry_escalation_intro="Versuche es diesmal anders:",
    examples_intro="Diese Absätze sind bereits gut verständlich. Schreibe im gleichen Stil:",
    context_summary="Worum es im ganzen Dokument geht: {summary}",
    context_previous="Vorheriger Absatz (nur zur Information, NICHT umschreiben):",
    context_following="Folgender Absatz (nur zur Information, NICHT umschreiben):",
    context_only_target="Schreibe AUSSCHLIESSLICH den Text in <schwer-verständlicher-text> um. Gib die Nachbarabsätze nicht aus.",
    prompt_intro="Hier ist ein schwer verständlicher Text, den du vollständig in Einfache Sprache, Sprachniveau B1 bis A2, umschreiben sollst:",
    prompt_rules_intro="Bitte lies den Text sorgfältig durch und schreibe ihn vollständig in Einfache Sprache um.\n\nBeachte dabei folgende Regeln:",
    prompt_outro="Formuliere den Text jetzt in Einfache Sprache, Sprachniveau B1 bis A2, um. Gib nur den umgeschriebenen Text aus.",
)

_LABELS_GENERIC = _Labels(
    scoring_intro="The text is scored automatically for readability ({label}).",
    current_score="Current: {current}.",
    target="Target: {target}.",
    issues_intro="These paragraphs are still too hard to read:",
    issue_item='- Paragraph {index}: "{text}"{meta}',
    retry_heading="Previous attempt",
    retry_intro="Your attempt {attempt} did not reach the target yet.",
    retry_previous="Your previous version:",
    retry_score="Score of your previous version: {current}.",
    retry_missing="The following information from the original text was missing in your previous version. It must be present this time:",
    retry_escalation_intro="Try a different approach this time:",
    examples_intro="These paragraphs are already easy to read. Write in the same style:",
    context_summary="What the whole document is about: {summary}",
    context_previous="Previous paragraph (for context only, do NOT rewrite it):",
    context_following="Following paragraph (for context only, do NOT rewrite it):",
    context_only_target="Rewrite ONLY the text inside <hard-to-read-text>. Do not output the neighbouring paragraphs.",
    prompt_intro="Here is a hard-to-read text that you must rewrite completely so that it is easy to read and easy to understand:",
    prompt_rules_intro="Read the text carefully and rewrite all of it.\n\nFollow these rules:",
    prompt_outro="Now rewrite the text so that it is easy to read. Output only the rewritten text.",
)

_ESCALATION_DE: tuple[tuple[str, ...], ...] = (
    (
        "Schreibe kürzere Sätze: höchstens 12 Wörter pro Satz.",
        "Ersetze schwierige und seltene Wörter durch einfache, häufige Wörter.",
        "Teile jeden Satz auf, der mehr als einen Gedanken enthält.",
    ),
    (
        "Schreibe sehr kurze Sätze: höchstens 10 Wörter pro Satz.",
        "Löse jeden Nebensatz in einen eigenen Hauptsatz auf.",
        "Ersetze jedes lange oder seltene Wort, für das es ein einfacheres gibt.",
        "Mache aus jedem langen Absatz mehrere kurze Absätze.",
    ),
)

_ESCALATION_GENERIC: tuple[tuple[str, ...], ...] = (
    (
        "Use shorter sentences (max 12 words per sentence).",
        "Replace complex or uncommon words with simple alternatives.",
        "Break compound sentences into multiple simple ones.",
    ),
    (
        "Use very short sentences (max 10 words per sentence).",
        "Turn every subordinate clause into its own sentence.",
        "Replace every long or uncommon word that has a simpler alternative.",
        "Split every long paragraph into several short ones.",
    ),
)


# =============================================================================
# HELPERS
# =============================================================================


def is_german(language: str | None) -> bool:
    """Return whether the authored German rule set applies to ``language``.

    >>> is_german("de")
    True
    >>> is_german("DE-CH")
    True
    >>> is_german("fr"), is_german(None)
    (False, False)
    """
    if not language:
        return False
    return language.strip().lower().split("-")[0] == GERMAN


def _labels(language: str | None) -> _Labels:
    return _LABELS_DE if is_german(language) else _LABELS_GENERIC


def _truncate(text: str, limit: int) -> str:
    """Shorten ``text`` to ``limit`` characters, blokkli-style.

    >>> _truncate("abcdef", 3)
    'abc...'
    >>> _truncate("abc", 3)
    'abc'
    """
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + "..."


def format_score(score: float | None, label: str) -> str:
    """Render a single score value with its metric label.

    >>> format_score(-1.25, "ZIX")
    'ZIX -1.2'
    >>> format_score(None, "ZIX")
    ''
    """
    if score is None:
        return ""
    return f"{label} {score:.1f}"


def _describe(score: float | None, band: str | None, cefr: str | None, label: str) -> str:
    """Render score, band and CEFR level as one human-readable phrase.

    >>> _describe(-1.2, "hard", "C1", "ZIX")
    'C1 (ZIX -1.2, hard)'
    >>> _describe(42.0, None, None, "LIX")
    'LIX 42.0'
    """
    scored = format_score(score, label)
    details = [part for part in (scored, band) if part]
    if cefr:
        return f"{cefr} ({', '.join(details)})" if details else cefr
    return ", ".join(details)


def _section(*lines: str) -> str:
    return "\n".join(line for line in lines if line)


# =============================================================================
# BLOCK RENDERERS
# =============================================================================


def render_score_reference_block(reference: ScoreReference | None, language: str | None = None) -> str:
    """Render the score-reference block (blokkli's ``getAgentContext``).

    Returns an empty string when there is nothing to say, so the caller can insert it
    unconditionally.

    >>> render_score_reference_block(None)
    ''
    >>> print(render_score_reference_block(
    ...     ScoreReference(label="ZIX", score=-3.8, band="hard", cefr="C1",
    ...                    scale="-10 bis 10", target="Sprachniveau A2 oder B1 (ZIX 0 oder höher)"),
    ...     "de"))
    <bewertung>
    Der Text wird automatisch auf Verständlichkeit bewertet (ZIX, -10 bis 10).
    Ziel: Sprachniveau A2 oder B1 (ZIX 0 oder höher).
    Aktuell: C1 (ZIX -3.8, hard).
    </bewertung>
    """
    if reference is None:
        return ""

    labels = _labels(language)
    label_with_scale = f"{reference.label}, {reference.scale}" if reference.scale else reference.label
    lines = [labels.scoring_intro.format(label=label_with_scale)]

    if reference.target:
        lines.append(labels.target.format(target=reference.target))

    current = _describe(reference.score, reference.band, reference.cefr, reference.label)
    if current:
        lines.append(labels.current_score.format(current=current))

    if reference.reference_table:
        lines.append(reference.reference_table.strip())

    tag = "bewertung" if is_german(language) else "scoring"
    return _section(f"<{tag}>", *lines, f"</{tag}>")


def render_issue_list(
    issues: Sequence[ParagraphIssue],
    score_label: str = "score",
    language: str | None = None,
) -> str:
    """Render the per-paragraph issue list — the mechanism that makes the loop work.

    >>> print(render_issue_list(
    ...     [ParagraphIssue(index=3, text="Ein sehr langer Schachtelsatz.", score=-4.1,
    ...                     band="hard", impact="hoch")],
    ...     "ZIX", "de"))
    <probleme>
    Diese Absätze sind noch zu schwer verständlich:
    - Absatz 3: «Ein sehr langer Schachtelsatz.» [ZIX -4.1, hard, Auswirkung: hoch]
    </probleme>
    >>> render_issue_list([], "ZIX", "de")
    ''
    """
    if not issues:
        return ""

    labels = _labels(language)
    german = is_german(language)
    impact_key = "Auswirkung" if german else "impact"

    lines: list[str] = [labels.issues_intro]
    for issue in issues:
        meta_parts = [
            part
            for part in (
                format_score(issue.score, score_label),
                issue.band or "",
                f"{impact_key}: {issue.impact}" if issue.impact else "",
            )
            if part
        ]
        meta = f" [{', '.join(meta_parts)}]" if meta_parts else ""
        lines.append(
            labels.issue_item.format(
                index=issue.index,
                text=_truncate(issue.text, MAX_ORIGINAL_CHARS),
                meta=meta,
            )
        )

    tag = "probleme" if german else "issues"
    return _section(f"<{tag}>", *lines, f"</{tag}>")


def escalation_instructions(attempt: int, language: str | None = None) -> tuple[str, ...]:
    """Return the escalating retry instructions for ``attempt``.

    ``attempt`` is the number of the attempt that just failed, so the first retry gets
    the mild set and every later retry the strict set (blokkli escalates to
    "max 10-12 words per sentence"; we split that into two levels).

    >>> escalation_instructions(1, "de")[0]
    'Schreibe kürzere Sätze: höchstens 12 Wörter pro Satz.'
    >>> escalation_instructions(2, "de")[0]
    'Schreibe sehr kurze Sätze: höchstens 10 Wörter pro Satz.'
    >>> escalation_instructions(9, "en")[0]
    'Use very short sentences (max 10 words per sentence).'
    """
    levels = _ESCALATION_DE if is_german(language) else _ESCALATION_GENERIC
    index = min(max(attempt, 1), len(levels)) - 1
    return levels[index]


def render_retry_block(
    previous: PreviousAttempt | None,
    score_label: str = "score",
    language: str | None = None,
) -> str:
    """Render the retry block: previous attempt, its score, missing facts, escalation.

    Mirrors blokkli's ``retryFields`` construction. Returns an empty string on attempt 1.

    >>> print(render_retry_block(
    ...     PreviousAttempt(attempt=1, text="Zu langer Satz.", score=-1.2, band="ok",
    ...                     missing_facts=["Frist: 30. Juni"]),
    ...     "ZIX", "de"))
    <vorheriger-versuch>
    Dein Versuch 1 hat das Ziel noch nicht erreicht.
    Bewertung deiner vorherigen Fassung: ZIX -1.2, ok.
    Deine vorherige Fassung:
    «Zu langer Satz.»
    Diese Informationen aus dem Originaltext haben in deiner vorherigen Fassung gefehlt. Sie müssen diesmal vollständig vorkommen:
    - Frist: 30. Juni
    Versuche es diesmal anders:
    - Schreibe kürzere Sätze: höchstens 12 Wörter pro Satz.
    - Ersetze schwierige und seltene Wörter durch einfache, häufige Wörter.
    - Teile jeden Satz auf, der mehr als einen Gedanken enthält.
    </vorheriger-versuch>
    >>> render_retry_block(None, "ZIX", "de")
    ''
    """
    if previous is None:
        return ""

    labels = _labels(language)
    german = is_german(language)
    quote_open, quote_close = ("«", "»") if german else ('"', '"')

    lines: list[str] = [labels.retry_intro.format(attempt=previous.attempt)]

    current = _describe(previous.score, previous.band, None, score_label)
    if current:
        lines.append(labels.retry_score.format(current=current))

    lines.append(labels.retry_previous)
    lines.append(f"{quote_open}{_truncate(previous.text, MAX_ORIGINAL_CHARS)}{quote_close}")

    if previous.missing_facts:
        lines.append(labels.retry_missing)
        lines.extend(f"- {fact.strip()}" for fact in previous.missing_facts)

    lines.append(labels.retry_escalation_intro)
    lines.extend(f"- {instruction}" for instruction in escalation_instructions(previous.attempt, language))

    tag = "vorheriger-versuch" if german else "previous-attempt"
    return _section(f"<{tag}>", *lines, f"</{tag}>")


def render_passing_examples(
    examples: Sequence[PassingExample],
    score_label: str = "score",
    language: str | None = None,
    limit: int = 2,
) -> str:
    """Render up to ``limit`` in-target paragraphs as exemplars (blokkli ``passingFields``).

    >>> print(render_passing_examples(
    ...     [PassingExample(index=1, text="Sie müssen nichts tun.", score=2.4)], "ZIX", "de"))
    <gelungene-beispiele>
    Diese Absätze sind bereits gut verständlich. Schreibe im gleichen Stil:
    - Absatz 1: «Sie müssen nichts tun.» [ZIX 2.4]
    </gelungene-beispiele>
    >>> render_passing_examples([], "ZIX", "de")
    ''
    """
    selected = list(examples)[: max(limit, 0)]
    if not selected:
        return ""

    labels = _labels(language)
    german = is_german(language)
    prefix = "Absatz" if german else "Paragraph"
    quote_open, quote_close = ("«", "»") if german else ('"', '"')

    lines: list[str] = [labels.examples_intro]
    for example in selected:
        scored = format_score(example.score, score_label)
        meta = f" [{scored}]" if scored else ""
        text = _truncate(example.text, MAX_EXAMPLE_CHARS)
        lines.append(f"- {prefix} {example.index}: {quote_open}{text}{quote_close}{meta}")

    tag = "gelungene-beispiele" if german else "passing-examples"
    return _section(f"<{tag}>", *lines, f"</{tag}>")


def render_neighbour_context(context: NeighbourContext | None, language: str | None = None) -> str:
    """Render the CHUNKED-mode neighbour block: read-only surroundings plus a scope guard.

    >>> print(render_neighbour_context(
    ...     NeighbourContext(previous_text="Vorher.", following_text="Nachher.",
    ...                      document_summary="Ein Merkblatt zur Baubewilligung."), "de"))
    <kontext>
    Worum es im ganzen Dokument geht: Ein Merkblatt zur Baubewilligung.
    Vorheriger Absatz (nur zur Information, NICHT umschreiben):
    «Vorher.»
    Folgender Absatz (nur zur Information, NICHT umschreiben):
    «Nachher.»
    Schreibe AUSSCHLIESSLICH den Text in <schwer-verständlicher-text> um. Gib die Nachbarabsätze nicht aus.
    </kontext>
    >>> render_neighbour_context(NeighbourContext(), "de")
    ''
    """
    if context is None:
        return ""
    if not (context.previous_text or context.following_text or context.document_summary):
        return ""

    labels = _labels(language)
    german = is_german(language)
    quote_open, quote_close = ("«", "»") if german else ('"', '"')

    lines: list[str] = []
    if context.document_summary:
        lines.append(labels.context_summary.format(summary=context.document_summary.strip()))
    if context.previous_text:
        lines.append(labels.context_previous)
        lines.append(f"{quote_open}{_truncate(context.previous_text, MAX_ORIGINAL_CHARS)}{quote_close}")
    if context.following_text:
        lines.append(labels.context_following)
        lines.append(f"{quote_open}{_truncate(context.following_text, MAX_ORIGINAL_CHARS)}{quote_close}")
    lines.append(labels.context_only_target)

    tag = "kontext" if german else "context"
    return _section(f"<{tag}>", *lines, f"</{tag}>")


# =============================================================================
# WHOLE PROMPT
# =============================================================================


def select_rules(language: str | None) -> str:
    """Return the rule block for ``language``: authored German, or language-neutral.

    >>> select_rules("de").startswith("# SPRACHREGELN")
    True
    >>> select_rules("fr").startswith("# HOW TO SIMPLIFY")
    True
    """
    return SIMPLIFY_STYLE_DE if is_german(language) else GENERIC_SIMPLIFY_INSTRUCTIONS


def build_system_message(language: str | None) -> str:
    """Return the system message for ``language``.

    >>> build_system_message("de") is not build_system_message("it")
    True
    """
    return SYSTEM_MESSAGE_ES if is_german(language) else GENERIC_SYSTEM_MESSAGE


def build_rewrite_prompt(
    text: str,
    language: str | None = GERMAN,
    *,
    score_reference: ScoreReference | None = None,
    issues: Sequence[ParagraphIssue] = (),
    previous_attempt: PreviousAttempt | None = None,
    passing_examples: Sequence[PassingExample] = (),
    neighbour_context: NeighbourContext | None = None,
    exemplar_limit: int = 2,
) -> str:
    """Assemble the full rewrite prompt from whatever data the caller has.

    Only ``text`` is required: with no other arguments this produces the single-shot
    prompt, equivalent in structure to ``CLAUDE_TEMPLATE_ES``. Each further argument adds
    exactly one block, in the order score reference → issues → retry → exemplars →
    neighbour context, before the rules and the closing instruction.

    ``score_reference.label`` is used to label every score in the prompt, so the metric
    name stays consistent across blocks.

    >>> prompt = build_rewrite_prompt("Ein schwieriger Text.", "de")
    >>> "<schwer-verständlicher-text>" in prompt
    True
    >>> "# SPRACHREGELN" in prompt
    True
    >>> "<bewertung>" in prompt
    False
    """
    labels = _labels(language)
    german = is_german(language)
    score_label = score_reference.label if score_reference else "score"
    text_tag = "schwer-verständlicher-text" if german else "hard-to-read-text"

    blocks: list[str] = [
        labels.prompt_intro,
        f"<{text_tag}>\n{text.strip()}\n</{text_tag}>",
        render_score_reference_block(score_reference, language),
        render_issue_list(issues, score_label, language),
        render_retry_block(previous_attempt, score_label, language),
        render_passing_examples(passing_examples, score_label, language, exemplar_limit),
        render_neighbour_context(neighbour_context, language),
        labels.prompt_rules_intro,
        REWRITE_COMPLETE if german else "",
        select_rules(language),
        labels.prompt_outro,
    ]

    return "\n\n".join(block for block in blocks if block).strip()
