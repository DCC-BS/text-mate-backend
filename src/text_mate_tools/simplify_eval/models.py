"""Data model of the simplify eval harness.

Three groups of types live here:

* :class:`SimplifyEvalCase` — the on-disk corpus schema (``evals/simplify/cases/*.json``).
* :class:`Simplifier` / :class:`Scorer` — the two narrow interfaces the runner is driven
  through. Nothing in this package imports the simplify pipeline: the pipeline does not
  exist yet (docs/simplify_redesign.md phases 2-5), so the harness depends only on these
  Protocols and today's single-shot quick action is injected as one implementation of them.
* :class:`CaseRunResult` — one simplification of one case, everything
  :mod:`text_mate_tools.simplify_eval.scoring` needs to aggregate.

See docs/simplify_redesign.md §6.
"""

from typing import Literal, Protocol, final

from pydantic import BaseModel, Field

SimplifyMode = Literal["whole", "chunked"]
"""Rewrite unit chosen for a text — docs/simplify_redesign.md §4.1.

``whole``   one LLM call over the entire text (the default path),
``chunked`` per-paragraph rewrites, used only above the chunking threshold.
"""

ReadabilityBand = Literal["easy", "ok", "hard"]
"""Calibrated band of a readability score — docs/simplify_redesign.md §4.2."""

CHUNKING_THRESHOLD_CHARS = 10000
"""Default ``simplify_chunking_threshold_chars`` (§14.5); the runner exposes ``--threshold``.

Raised from 8000 after §13.6 measured that 12 of 16 real Basel-Stadt documents exceed it.
"""

PARAGRAPH_SEPARATOR = "\n\n"
"""How the client separates blocks (``useBaseEditor.ts`` ``editor.getText()``)."""

Provenance = Literal["real", "adapted", "synthetic"]
"""Where a case's text came from — the difference between evidence and illustration.

``real``       verbatim from a published public document; ``source_url`` identifies it.
``adapted``    real Behörden register, but reused from another corpus in this repo
               rather than published as such.
``synthetic``  written for the harness. Numbers from these cases illustrate that the
               code path runs; they are not evidence about Behörden prose.

The default is ``synthetic`` on purpose: a case that forgets to declare its provenance
must understate its own authority, never overstate it.
"""


@final
class SimplifyEvalCase(BaseModel):
    """One corpus text with its recorded source readability.

    Unlike the advisor harness there is no hand-labelling to do: the analyzer is itself
    the scorer. ``source_score`` / ``source_band`` are therefore a *recorded observation*
    rather than ground truth — the runner recomputes them and reports drift.

    >>> case = SimplifyEvalCase(id="x", source_text="a" * 10)
    >>> case.language, case.char_count, case.expected_mode()
    ('de', 10, 'whole')
    >>> SimplifyEvalCase(id="y", source_text="a" * 11000).expected_mode()
    'chunked'
    """

    id: str = Field(description="Unique case identifier; matches the file stem by convention")
    source_text: str = Field(description="The verbatim source text, paragraphs separated by blank lines")
    language: str = Field(default="de", description="ISO 639-1 code of the source text")
    source_score: float | None = Field(
        default=None,
        description="Readability score of the source when the case was authored (ZIX for German); null if unrecorded",
    )
    source_band: ReadabilityBand | None = Field(
        default=None,
        description="Band of source_score; null if unrecorded",
    )
    notes: str = Field(default="", description="What this case is probing")
    provenance: Provenance = Field(
        default="synthetic",
        description="real | adapted | synthetic — see the Provenance alias; defaults to the weakest claim",
    )
    source_url: str = Field(
        default="",
        description="URL of the published document; required when provenance is 'real'",
    )
    source_document: str = Field(
        default="",
        description="Human-readable title or filename of the source document",
    )
    must_keep_facts: list[str] = Field(
        default_factory=list,
        description=(
            "Verbatim substrings of source_text that must survive simplification "
            "(dates, deadlines, amounts, names). The real measure of information loss; "
            "length ratio is only a crude proxy (§11)."
        ),
    )
    must_keep_facts_reviewed: bool = Field(
        default=False,
        description=(
            "False means the facts were extracted programmatically and NOT yet checked by a "
            "human: they are candidates. A machine can tell that '15. Dezember 2026' is a date; "
            "it cannot tell whether losing it matters. Fidelity numbers over unreviewed facts "
            "are indicative only."
        ),
    )

    @property
    def char_count(self) -> int:
        return len(self.source_text)

    @property
    def is_evidence(self) -> bool:
        """True when this case's numbers may be cited as evidence about real Behörden prose.

        >>> SimplifyEvalCase(id="a", source_text="x", provenance="real").is_evidence
        True
        >>> SimplifyEvalCase(id="b", source_text="x").is_evidence
        False
        """
        return self.provenance == "real"

    def paragraphs(self) -> list[str]:
        """Split on blank lines, dropping empties — the §4.1 Stage 0 split.

        The real classifier (heading / list_item / paragraph) is T2.5; the harness only
        needs the units it must score.

        >>> SimplifyEvalCase(id="p", source_text="Eins.\\n\\n\\nZwei.").paragraphs()
        ['Eins.', 'Zwei.']
        """
        return [p.strip() for p in self.source_text.split(PARAGRAPH_SEPARATOR) if p.strip()]

    def expected_mode(self, threshold: int = CHUNKING_THRESHOLD_CHARS) -> SimplifyMode:
        """Mode the pipeline would select for this case at ``threshold``."""
        return "whole" if self.char_count <= threshold else "chunked"


@final
class SimplifyOutput(BaseModel):
    """What a simplifier returns to the harness.

    Every field except ``text`` has a default that describes today's single-shot agent
    (one call, one attempt, no gates), so the baseline adapter only has to fill in the
    text. The Phase 4 loop fills in the rest.
    """

    text: str = Field(description="The full simplified text")
    attempts: int = Field(default=1, ge=1, description="Rewrite attempts made (§9 simplify_max_attempts)")
    llm_calls: int = Field(default=1, ge=0, description="Total LLM calls (§8)")
    converged: bool = Field(
        default=True,
        description="Whether the assembled text reached the target band (§4.1 Stage 3)",
    )
    fidelity_failures: int = Field(
        default=0,
        ge=0,
        description=(
            "Attempts rejected by a runtime fidelity gate. Always 0: the LLM gate was "
            "measured and removed. Information loss is measured against the case's "
            "must_keep_facts instead. Kept so a future gate has somewhere to report."
        ),
    )
    mode: SimplifyMode | None = Field(
        default=None,
        description="Mode the simplifier actually used; null lets the harness derive it from source length",
    )
    unconverged_units: list[int] = Field(
        default_factory=list,
        description=(
            "Indices of merged, scorable units (docs/simplify_redesign.md section 14.2) that "
            "never reached the target band (CHUNKED mode). Mirrors "
            "``text_mate_backend.models.simplify_models.SimplifyOutcome.unconverged_units``."
        ),
    )


class Simplifier(Protocol):
    """The one thing the runner needs: text in, simplified text out.

    Deliberately narrower than any concrete service. `run_simplify_eval.py` ships two
    implementations — the current single-shot quick action (the Phase 1 baseline) and a
    passthrough used to smoke-test the harness without an LLM — and the Phase 4
    ``SimplifyService`` becomes a third without changing anything here.
    """

    name: str

    async def __call__(self, text: str, language: str) -> SimplifyOutput: ...


class Scorer(Protocol):
    """Readability scoring, as the Phase 2 ``ReadabilityAnalyzer`` Protocol will expose it.

    Subset of docs/simplify_redesign.md §4.2, kept async because ZIX is a CPU-bound
    spaCy + sklearn call that the backend runs off the event loop.
    """

    score_label: str
    min_words: int

    async def score(self, text: str) -> float | None: ...

    def band(self, score: float) -> ReadabilityBand: ...

    def cefr(self, score: float) -> str | None: ...


@final
class CaseRunResult(BaseModel):
    """One simplification of one case: everything the metrics of §6 are computed from."""

    case_id: str
    run_index: int = Field(default=0, ge=0, description="0-based index within --runs N")
    mode: SimplifyMode = "whole"
    language: str = "de"
    score_label: str = "ZIX"

    source_chars: int = 0
    result_chars: int = 0

    score_before: float | None = None
    score_after: float | None = None
    band_before: ReadabilityBand | None = None
    band_after: ReadabilityBand | None = None
    cefr_before: str | None = None
    cefr_after: str | None = None

    paragraphs_total: int = 0
    paragraphs_scored: int = Field(default=0, description="Paragraphs long enough to score (min_words)")
    paragraphs_in_target_before: int = 0
    paragraphs_in_target_after: int = 0

    attempts: int = 1
    converged: bool = True
    unconverged_units: list[int] = Field(
        default_factory=list,
        description=(
            "Indices of merged, scorable units (section 14.2) that never reached the target "
            "band. This is what T6.7 surfaces to the user, so its length on real documents is "
            "a UX signal, not just a metric. Note it can legitimately be empty while "
            "`converged` is False: a whole-document ZIX score is not the mean of its units "
            "(see section 13.6)."
        ),
    )
    fidelity_failures: int = 0
    missing_facts: list[str] = Field(
        default_factory=list,
        description=(
            "must_keep_facts absent from the simplified text, compared after normalizing "
            "both sides (simplify_eval/normalize.py) so a legitimate 'dreissig Tagen' -> "
            "'30 Tagen' is not reported as a loss. An observation, never a gate."
        ),
    )
    llm_calls: int = 1
    wall_clock_seconds: float = 0.0
    error: str | None = Field(default=None, description="Set when the simplifier raised; the run still counts")

    @property
    def score_delta(self) -> float | None:
        """After minus before, on the analyzer's raw scale (higher = easier for ZIX)."""
        if self.score_before is None or self.score_after is None:
            return None
        return self.score_after - self.score_before

    @property
    def length_ratio(self) -> float | None:
        """Result chars / source chars. A crude information-loss proxy only (§11)."""
        if not self.source_chars:
            return None
        return self.result_chars / self.source_chars

    @property
    def in_target(self) -> bool:
        return self.band_after == "easy"

    @property
    def fidelity_ok(self) -> bool:
        """No gate rejection and no hand-listed must-keep fact lost."""
        return self.fidelity_failures == 0 and not self.missing_facts

    @property
    def paragraph_target_share_before(self) -> float | None:
        if not self.paragraphs_scored:
            return None
        return self.paragraphs_in_target_before / self.paragraphs_scored

    @property
    def paragraph_target_share_after(self) -> float | None:
        if not self.paragraphs_scored:
            return None
        return self.paragraphs_in_target_after / self.paragraphs_scored
