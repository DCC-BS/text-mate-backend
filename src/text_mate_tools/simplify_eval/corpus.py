"""Loading and validating the simplify eval corpus (``evals/simplify/cases/*.json``).

Validation is the same discipline as the advisor harness's ``validate_cases``: an eval
that silently measures a broken case is worse than no eval. Everything checked here is an
*authoring* error, never a model error — a fact that is not a substring of the source text
can never be found in the output, and a recorded band that contradicts its recorded score
means one of the two was edited by hand.

See ``evals/simplify/README.md`` for the schema and how to add a case.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import final

from text_mate_tools.simplify_eval.models import CHUNKING_THRESHOLD_CHARS, SimplifyEvalCase
from text_mate_tools.simplify_eval.scoring import (
    german_band,
    score_gap_to_target,
)

DEFAULT_CASES_DIR = Path("evals/simplify/cases")

TYPICAL_SINGLE_PASS_GAIN = 3.2
"""ZIX points one single-shot rewrite gained in the probe that motivated corpus collection.

Source: a hard one-sentence probe scored -6.2 (C2) and came back at -3.0 (C1). It is an
*observation on one text with one model*, used only to flag a corpus that cannot possibly
discriminate — never as a threshold anything passes or fails on. Re-measure it when the
model or the prompt changes.
"""


def load_cases(directory: Path, case_ids: Sequence[str] = ()) -> list[SimplifyEvalCase]:
    """Load every ``*.json`` case in ``directory``, optionally filtered to ``case_ids``.

    Raises ``ValueError`` when the directory holds no cases or an id is unknown, and
    ``pydantic.ValidationError`` when a file does not match the schema.
    """
    files = sorted(directory.glob("*.json"))
    if not files:
        raise ValueError(f"No eval case files found in {directory}")
    cases = [SimplifyEvalCase.model_validate_json(f.read_text(encoding="utf-8")) for f in files]
    if case_ids:
        wanted = set(case_ids)
        cases = [c for c in cases if c.id in wanted]
        missing = wanted - {c.id for c in cases}
        if missing:
            raise ValueError(f"Unknown case ids: {', '.join(sorted(missing))}")
    return cases


def validate_cases(cases: Sequence[SimplifyEvalCase]) -> list[str]:
    """Return every authoring problem found; an empty list means the corpus is usable.

    >>> validate_cases([SimplifyEvalCase(id="a", source_text="Kurzer Text.")])
    []
    >>> validate_cases([SimplifyEvalCase(id="a", source_text="Text.", must_keep_facts=["1.1.2026"])])
    ["Case 'a': must-keep fact '1.1.2026' is not a substring of source_text"]
    """
    errors: list[str] = []
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            errors.append(f"Duplicate case id '{case.id}'")
        seen.add(case.id)

        if not case.source_text.strip():
            errors.append(f"Case '{case.id}': source_text is empty")

        for fact in case.must_keep_facts:
            if fact not in case.source_text:
                errors.append(f"Case '{case.id}': must-keep fact '{fact}' is not a substring of source_text")

        if case.provenance == "real" and not case.source_url:
            errors.append(f"Case '{case.id}': provenance is 'real' but no source_url identifies the document")

        if case.source_score is not None and case.source_band is not None and case.language == "de":
            recomputed = german_band(case.source_score)
            if recomputed != case.source_band:
                errors.append(
                    f"Case '{case.id}': source_band '{case.source_band}' contradicts "
                    f"source_score {case.source_score} (expected '{recomputed}')"
                )
    return errors


@final
@dataclass(frozen=True)
class CorpusCoverage:
    """What the corpus does and does not span — printed in the report header.

    The spec asks for 20-30 texts spanning easy to very hard and spanning the chunking
    threshold so both modes are exercised (§6). This makes the gap between that and the
    corpus on disk a visible number rather than an assumption.
    """

    cases: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    modes: dict[str, int] = field(default_factory=dict)
    bands: dict[str, int] = field(default_factory=dict)
    provenance: dict[str, int] = field(default_factory=dict)
    min_chars: int = 0
    max_chars: int = 0
    with_must_keep_facts: int = 0
    unreviewed_facts: int = 0
    scores: dict[str, tuple[float, ...]] = field(default_factory=dict)
    """Every recorded source score grouped by language, ascending — the distribution the harness can measure over."""

    @property
    def real_cases(self) -> int:
        return self.provenance.get("real", 0)

    def gap_to_target(self, language: str | None = None) -> tuple[float, ...]:
        """How far below the easy floor each scored case sits, ascending.

        When ``language`` is given, computes gaps only for that language.
        Otherwise computes gaps across all languages using each language's target threshold.
        """
        if language is not None:
            return tuple(sorted(score_gap_to_target(score, language) for score in self.scores.get(language, ())))
        gaps = [score_gap_to_target(score, lang) for lang, lang_scores in self.scores.items() for score in lang_scores]
        return tuple(sorted(gaps))

    def beyond_single_pass(self, typical_pass_gain: float, language: str | None = None) -> int:
        """Cases whose gap to target exceeds what one rewrite pass typically gains.

        ``typical_pass_gain`` is an *observed* figure, not a constant: it must be
        re-measured whenever the model or the prompt changes.
        """
        return sum(1 for gap in self.gap_to_target(language) if gap > typical_pass_gain)

    def shortfalls(self, target_cases: int = 20, typical_pass_gain: float = TYPICAL_SINGLE_PASS_GAIN) -> list[str]:
        """Human-readable warnings about corpus gaps. Never fatal."""
        warnings: list[str] = []
        if self.cases < target_cases:
            warnings.append(
                f"corpus holds {self.cases} case(s); docs/simplify_redesign.md §6 asks for {target_cases}-30"
            )
        if self.real_cases < self.cases:
            warnings.append(
                f"only {self.real_cases}/{self.cases} case(s) are verbatim published documents "
                f"(provenance {self.provenance}); the rest illustrate, they do not evidence"
            )
        for mode in ("whole", "chunked"):
            if not self.modes.get(mode):
                warnings.append(f"no case exercises {mode.upper()} mode")
        if len(self.bands) < 2:
            warnings.append("corpus does not span multiple source bands (easy -> very hard is required)")
        total_scored = sum(len(s) for s in self.scores.values())
        if total_scored and not self.beyond_single_pass(typical_pass_gain):
            warnings.append(
                f"no case sits more than {typical_pass_gain:.1f} ZIX below target, so a single-shot rewrite "
                "should reach target on all of them — this corpus cannot separate one shot from a loop"
            )
        if self.unreviewed_facts:
            warnings.append(
                f"{self.unreviewed_facts} case(s) carry auto-extracted must-keep facts awaiting human review; "
                "fidelity numbers over them are indicative only"
            )
        return warnings


def coverage(cases: Sequence[SimplifyEvalCase], threshold: int = CHUNKING_THRESHOLD_CHARS) -> CorpusCoverage:
    """Summarize what the corpus spans.

    >>> c = coverage([SimplifyEvalCase(id="a", source_text="x" * 100, source_score=-3.0)])
    >>> c.cases, c.modes, c.bands
    (1, {'whole': 1}, {'hard': 1})
    """
    languages: dict[str, int] = {}
    modes: dict[str, int] = {}
    bands: dict[str, int] = {}
    provenance: dict[str, int] = {}
    scores: dict[str, list[float]] = {}
    for case in cases:
        languages[case.language] = languages.get(case.language, 0) + 1
        provenance[case.provenance] = provenance.get(case.provenance, 0) + 1
        mode = case.expected_mode(threshold)
        modes[mode] = modes.get(mode, 0) + 1
        band = case.source_band
        if band is None and case.language == "de" and case.source_score is not None:
            band = german_band(case.source_score)
        if band is not None:
            bands[band] = bands.get(band, 0) + 1
        if case.source_score is not None:
            scores.setdefault(case.language, []).append(case.source_score)
    lengths = [case.char_count for case in cases]
    return CorpusCoverage(
        cases=len(cases),
        languages=languages,
        modes=modes,
        bands=bands,
        provenance=provenance,
        min_chars=min(lengths, default=0),
        max_chars=max(lengths, default=0),
        with_must_keep_facts=sum(1 for case in cases if case.must_keep_facts),
        unreviewed_facts=sum(1 for case in cases if case.must_keep_facts and not case.must_keep_facts_reviewed),
        scores={lang: tuple(sorted(s)) for lang, s in sorted(scores.items())},
    )
