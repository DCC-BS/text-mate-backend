"""Models of the simplification pipeline: agent I/O, stream events, run outcome.

Three groups live here, following the convention of ``models/rule_models.py``
(agent input/output models live next to the wire models, not inside the agents):

* :class:`RewriteRequest` — what the loop's one agent consumes
  (``docs/simplify_redesign.md`` section 5.3).
* The four stream events of ``POST /simplify`` (section 4.7). Their field names and
  their ``event`` discriminator are the wire contract with
  ``app/composables/useSimplify.ts``; a rename here needs a matching, coordinated
  change on the frontend (as with the ``paragraphs``/``paragraphs_in_target``/
  ``unconverged_paragraphs`` -> ``units``/``units_in_target``/``unconverged_units``
  rename below, section 14.4 -- the old names counted raw, unmerged blocks in one
  event and merged, scorable units in another, which is what let "42 of 258" reach a
  user as if the tool had barely touched the document).
* :class:`SimplifyOutcome` — the collected result of one run, for callers that
  want the answer rather than the stream (the eval harness, tests).

:class:`SimplifyOutcome` is deliberately field-compatible with
``text_mate_tools.simplify_eval.models.SimplifyOutput`` so the eval harness can
drive :class:`~text_mate_backend.services.simplify_service.SimplifyService`
through its ``Simplifier`` Protocol. The backend must not import from
``text_mate_tools`` (the dependency runs the other way), so the compatibility is
structural rather than an inheritance.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from text_mate_backend.readability.types import ReadabilityBand
from text_mate_backend.utils.simplify_prompt import (
    NeighbourContext,
    ParagraphIssue,
    PassingExample,
    PreviousAttempt,
    ScoreReference,
)

SimplifyMode = Literal["whole", "chunked"]
"""Rewrite unit chosen for a text (section 4.1).

``whole``   one LLM call over the entire text — the default path,
``chunked`` per-paragraph rewrites, used only above the chunking threshold.
"""

SimplifyStage = Literal["rewriting", "readability"]
"""What a ``progress`` event reports on.

``rewriting``   the model is producing text; the unit counter moves as units land,
``readability`` a round finished and its result has been measured.

The two are *phases*, not gates. Readability is still the only gate (there used to be
a second, ``"fidelity"``, an LLM claim check which measurement retired). ``rewriting``
exists because it is the phase that takes the wall-clock: without it the client had no
event between ``start`` and the end of the whole first round, so it sat on the
measurement label for minutes while the model was in fact rewriting.
"""


# =============================================================================
# REQUEST
# =============================================================================


class SimplifyInput(BaseModel):
    """Body of ``POST /simplify``."""

    text: str = Field(description="The text to simplify, paragraphs separated by blank lines")
    language: str | None = Field(
        default=None,
        description=(
            "The client's UI-locale hint (ISO 639-1). Detection from the text wins; "
            "the hint is only a fallback for texts too short to detect."
        ),
    )


# =============================================================================
# AGENT I/O
# =============================================================================


@dataclass(frozen=True, slots=True)
class RewriteRequest:
    """Everything the rewriter needs for one attempt.

    A plain dataclass rather than a pydantic model because it carries the prompt
    dataclasses of ``utils/simplify_prompt.py`` verbatim; it is agent *deps*, never
    serialised to the wire.
    """

    text: str
    language: str | None = None
    score_reference: ScoreReference | None = None
    issues: Sequence[ParagraphIssue] = ()
    previous_attempt: PreviousAttempt | None = None
    passing_examples: Sequence[PassingExample] = ()
    neighbour_context: NeighbourContext | None = None
    exemplar_limit: int = 2
    attempt: int = 1


# =============================================================================
# STREAM EVENTS (section 4.7)
# =============================================================================


class SimplifyStartEvent(BaseModel):
    """First event of every run: what was detected and how it will be processed."""

    event: Literal["start"] = "start"
    language: str | None = Field(description="Language the text is written in; null when detection was inconclusive")
    score_label: str | None = Field(default=None, description='Metric name ("ZIX", "LIX", ...); null when unscored')
    scored: bool = Field(description="False for languages with no analyzer: single rewrite, no loop, no score fields")
    mode: SimplifyMode = Field(description="whole (default) or chunked (above the threshold)")
    units: int = Field(
        description=(
            "Number of merged, scorable units (docs/simplify_redesign.md section 14.2) the "
            "gate will operate on -- not the count of raw blank-line-separated blocks in the "
            "source, which is typically 2-6x higher and is never itself gated on. This is the "
            "same population SimplifyProgressEvent.units_in_target is counted against."
        )
    )
    score_before: float | None = None
    band_before: ReadabilityBand | None = None
    cefr_before: str | None = None


class SimplifyProgressEvent(BaseModel):
    """One attempt has been measured. Purely informational; never final.

    Exactly one of these per attempt. There used to be two — one per gate — until the
    LLM fidelity gate was measured and removed.
    """

    event: Literal["progress"] = "progress"
    attempt: int = Field(description="1-based attempt number")
    stage: SimplifyStage
    score: float | None = None
    band: ReadabilityBand | None = None
    cefr: str | None = None
    units_in_target: int | None = Field(
        default=None,
        description=(
            "Merged, scorable units (section 14.2) whose band is easy, after this attempt -- "
            "counted over the same population SimplifyStartEvent.units reports, so the two "
            "numbers form one fraction ('X of Y units'), never a raw-paragraph numerator over "
            "a merged-unit denominator or vice versa."
        ),
    )


class SimplifyChunkDoneEvent(BaseModel):
    """A paragraph is finished (CHUNKED mode only).

    **Final.** It is emitted only once the paragraph can no longer change — either it
    reached the target band or the attempt budget ran out — because the UI never
    retracts text it has shown. Events may arrive out of order and are reassembled
    by ``index``.

    ``converged: false`` does **not** mean nothing changed: the best attempt ships
    either way, and ``text``/``score_after`` describe it. It means the unit is still
    outside the target band and deserves a human look.
    """

    event: Literal["chunk_done"] = "chunk_done"
    index: int = Field(description="Index of the unit in the source document")
    text: str = Field(description="Final text of this unit; may itself contain blank lines (1-in-N-out)")
    score_before: float | None = None
    score_after: float | None = Field(
        default=None, description="Null only when no attempt produced usable output and the unit is unchanged"
    )
    cefr_before: str | None = None
    cefr_after: str | None = None
    attempts: int = 1
    converged: bool = Field(
        description="False when the unit never reached the target band; its best rewrite still ships"
    )


class UnconvergedRange(BaseModel):
    """Half-open character range into ``SimplifyDoneEvent.text`` / ``SimplifyOutcome.text``.

    Deliberately indexes the **assembled output**, not the source: the frontend
    highlights the passage the user actually reads, and a unit's length changes
    between source and rewrite (one unit in, N paragraphs out) -- so the source
    offsets ``TextUnit.start``/``end`` are the wrong coordinate space here.

    Offsets are **UTF-16 code units**, matching the convention this project already
    established at the API boundary (JS strings are UTF-16) for ``ViolationRange`` in
    ``advisor.py``; see ``utils.text_offsets.to_utf16_offset`` for the code-point ->
    code-unit translation reused to build these.
    """

    start: int = Field(description="Start position (0-based, inclusive), UTF-16 code units, into `text`")
    end: int = Field(description="End position (exclusive), UTF-16 code units, into `text`")


class SimplifyDoneEvent(BaseModel):
    """Last event of every run; always carries the fully assembled text."""

    event: Literal["done"] = "done"
    text: str = Field(
        description=(
            "The complete simplified text. The best rewrite is returned even when it did "
            "not reach the target band; the original comes back only when no attempt "
            "produced usable output."
        )
    )
    language: str | None = None
    score_label: str | None = None
    scored: bool = True
    score_before: float | None = None
    score_after: float | None = None
    band_after: ReadabilityBand | None = None
    cefr_after: str | None = Field(default=None, description="CEFR level of score_after, where the metric has one")
    converged: bool = Field(
        default=True,
        description=(
            "True when no unit is left in unconverged_units (docs/simplify_redesign.md "
            "section 14.1). The gate lives on the unit, not the document: the whole-document "
            "band below is reported, never gated on, and converged can be true even when it "
            "reads 'ok' rather than 'easy'."
        ),
    )
    unconverged_units: list[int] = Field(
        default_factory=list,
        description="Indices of units that never reached the target band",
    )
    unconverged_ranges: list[UnconvergedRange] = Field(
        default_factory=list,
        description=(
            "Character ranges into `text`, one per entry of unconverged_units in the "
            "same order, for the frontend to highlight without re-deriving offsets from "
            "indices it cannot map back to the rewritten text itself."
        ),
    )
    rewrite_failures: int = Field(
        default=0,
        description=(
            "LLM rewrite calls that produced nothing usable (timeout, error, empty output). "
            "Non-zero means part of this result is unchanged source because the model could "
            "not be reached or did not answer -- NOT because the text needed no change. The "
            "two look identical in the diff, so the client needs this number to tell the user "
            "which one happened."
        ),
    )


SimplifyEvent = Annotated[
    SimplifyStartEvent | SimplifyProgressEvent | SimplifyChunkDoneEvent | SimplifyDoneEvent,
    Field(discriminator="event"),
]
"""Anything ``POST /simplify`` writes to the stream, one JSON object per line."""


# =============================================================================
# RUN OUTCOME
# =============================================================================


@dataclass(slots=True)
class SimplifyOutcome:
    """The collected result of one run.

    Field-compatible with the eval harness's ``SimplifyOutput`` (see the module
    docstring) plus the readability numbers the harness recomputes itself.
    """

    text: str
    attempts: int = 1
    llm_calls: int = 0
    rewrite_failures: int = 0
    converged: bool = True
    mode: SimplifyMode | None = None
    unconverged_units: list[int] = field(default_factory=list)
    unconverged_ranges: list[UnconvergedRange] = field(default_factory=list)

    language: str | None = None
    score_label: str | None = None
    scored: bool = True
    score_before: float | None = None
    score_after: float | None = None
    band_after: ReadabilityBand | None = None
    cefr_after: str | None = None
