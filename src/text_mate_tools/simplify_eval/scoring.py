"""Metrics for the simplify eval harness.

Every number required by docs/simplify_redesign.md §6 is computed here, from nothing but
a list of :class:`~text_mate_tools.simplify_eval.models.CaseRunResult`:

    score before/after (mean ± spread), band shift, CEFR shift where available,
    documents-in-target rate (primary), all-units-converged rate and the unconverged-units
    distribution (both secondary, §14.1/14.4), share of paragraphs reaching target,
    attempts-to-converge distribution, fidelity-failure rate, length ratio, wall-clock
    p50/p95, LLM call count

:func:`aggregate_by_mode` produces the same aggregate split into WHOLE and CHUNKED, which
is how the report is read: the two modes are different pipelines (§4.1) and averaging them
together hides both.

**Two numbers answer different questions and must never share a headline.**
``documents_in_target_rate`` is what the user experiences: did the assembled text they get
back read "easy"? ``all_units_converged_rate`` is a per-unit gate diagnostic: did the loop
run out of retries anywhere in the document? A big CHUNKED document can converge on every
metric a user would recognize while reading 0.0 on the second number, because one dense
paragraph out of dozens never cleared its own band (§13.6). Reporting the second number
first, or under a name that sounds like the first, has already produced a wrong "total
failure" reading of a run that mostly succeeded -- print ``documents_in_target_rate``
first, always, and keep the other clearly subordinate.

The German band calibration is **not** duplicated here: :func:`german_band` delegates to
``text_mate_backend.readability.languages.german``, which owns it (§4.2). Two copies of a
calibration are two chances to drift, and the harness must gate on exactly the thresholds
the pipeline gates on or it measures the wrong thing.
"""

import statistics
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from text_mate_backend.readability.languages.german import (
    BAND_CONFIG as GERMAN_BAND_CONFIG,
    GermanAnalyzer,
)
from text_mate_tools.simplify_eval.models import CaseRunResult, ReadabilityBand, SimplifyMode

GERMAN_ANALYZER = GermanAnalyzer()
"""The pipeline's own German analyzer — the single source of the ZIX calibration (§4.2)."""

BAND_ORDER: dict[ReadabilityBand, int] = {"hard": 0, "ok": 1, "easy": 2}
"""Ordinal scale for bands, ascending in easiness — a shift of +1 is one band easier."""

CEFR_ORDER: dict[str, int] = {"C2": 0, "C1": 1, "B2": 2, "B1": 3, "A2": 4, "A1": 5}
"""Ordinal scale for CEFR levels, ascending in easiness (A1 easiest)."""

GERMAN_EASY_MIN_ZIX = GERMAN_BAND_CONFIG.easy
"""ZIX >= 0 is the ZH/Bundeskanzlei "easy" floor and is exactly CEFR in {A1, A2, B1} (§2.1)."""

GERMAN_OK_MIN_ZIX = GERMAN_BAND_CONFIG.ok
"""``limit_medium`` from ``simply-simplify-language``'s config.yaml (§1.1)."""

GERMAN_MIN_WORDS = GERMAN_ANALYZER.min_words
"""ZIX warns at <= 5 words that the estimate is unreliable, so its floor for scoring is 6."""


def german_band(score: float) -> ReadabilityBand:
    """Classify a ZIX score into a calibrated band.

    Delegates to the backend's German analyzer so the harness and the pipeline can never
    disagree about what "easy" means.

    >>> german_band(1.4), german_band(0.0), german_band(-1.9), german_band(-3.8)
    ('easy', 'easy', 'ok', 'hard')
    """
    return GERMAN_ANALYZER.band(score)


def band_shift(before: ReadabilityBand | None, after: ReadabilityBand | None) -> int | None:
    """Bands moved towards "easy"; negative means the text got harder.

    >>> band_shift("hard", "easy"), band_shift("ok", "ok"), band_shift("easy", "hard")
    (2, 0, -2)
    >>> band_shift(None, "easy") is None
    True
    """
    if before is None or after is None:
        return None
    return BAND_ORDER[after] - BAND_ORDER[before]


def cefr_shift(before: str | None, after: str | None) -> int | None:
    """CEFR levels moved towards A1. ``None`` when either side is missing or unknown.

    ``fr`` and ``it`` have no CEFR mapping (§10), so this is absent for those languages
    by design rather than by failure.

    >>> cefr_shift("C1", "A2"), cefr_shift("B1", "B1")
    (3, 0)
    >>> cefr_shift("C1", "Klingonisch") is None
    True
    """
    if before not in CEFR_ORDER or after not in CEFR_ORDER:
        return None
    return CEFR_ORDER[str(after)] - CEFR_ORDER[str(before)]


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile, ``q`` in [0, 1]. Returns 0.0 for no values.

    >>> percentile([1, 2, 3, 4], 0.5)
    2.5
    >>> percentile([10.0], 0.95)
    10.0
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return float(ordered[low] + (ordered[high] - ordered[low]) * (position - low))


@dataclass(frozen=True)
class Stats:
    """Summary of one metric across runs. ``spread`` is the sample standard deviation."""

    n: int = 0
    mean: float = 0.0
    spread: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0

    def format_mean(self, digits: int = 2) -> str:
        """``mean ± spread``, or ``--`` when nothing was measured.

        >>> Stats().format_mean()
        '--'
        """
        if not self.n:
            return "--"
        return f"{self.mean:.{digits}f} ± {self.spread:.{digits}f}"


def summarize(values: Iterable[float]) -> Stats:
    """Summarize a metric; ``None`` values must be filtered out by the caller.

    >>> s = summarize([1.0, 2.0, 3.0])
    >>> s.n, s.mean, s.p50, s.minimum, s.maximum
    (3, 2.0, 2.0, 1.0, 3.0)
    >>> summarize([]).n
    0
    """
    materialized = [float(v) for v in values]
    if not materialized:
        return Stats()
    return Stats(
        n=len(materialized),
        mean=statistics.fmean(materialized),
        spread=statistics.stdev(materialized) if len(materialized) > 1 else 0.0,
        p50=percentile(materialized, 0.5),
        p95=percentile(materialized, 0.95),
        minimum=min(materialized),
        maximum=max(materialized),
    )


def _present(values: Iterable[float | None]) -> list[float]:
    return [v for v in values if v is not None]


@dataclass(frozen=True)
class AggregateMetrics:
    """The §6 metric set over a set of runs (one case, one mode, or the whole corpus)."""

    label: str = ""
    runs: int = 0
    cases: int = 0
    errors: int = 0

    score_before: Stats = field(default_factory=Stats)
    score_after: Stats = field(default_factory=Stats)
    score_delta: Stats = field(default_factory=Stats)

    band_shift: Stats = field(default_factory=Stats)
    band_after_counts: dict[str, int] = field(default_factory=dict)
    cefr_shift: Stats = field(default_factory=Stats)

    documents_in_target_rate: float = 0.0
    """PRIMARY success measure: share of runs whose *assembled* text reached the target
    band (``CaseRunResult.in_target``, i.e. ``band_after == "easy"``). This is the one
    number the user experiences -- the score badge in the diff header -- so it is what
    the report leads with and what T7.1 tunes against.

    Do not read this as "the run converged": docs/simplify_redesign.md §14.1 moved the
    gate to the unit, so a document can be in target here while :attr:`all_units_converged_rate`
    below is 0 for the same run (one unit still short, section 14.4's "nothing to point
    at" case) -- and, more commonly on real CHUNKED documents, the reverse: every unit
    converged (see the field below) while this number is still under threshold, because a
    whole-document score is not the mean of its units (§13.6). Renamed from ``in_target_rate``.
    """

    all_units_converged_rate: float = 0.0
    """SECONDARY, diagnostic only: share of runs in which *every* scorable unit reached
    target (``CaseRunResult.converged``). This is the section 14.1 per-unit gate result,
    not a verdict on the run -- it is the signal behind the ``unconverged_units``
    shortfall hint (T6.7), nothing else. On a large CHUNKED document one stubborn block
    out of dozens is enough to read 0 here while :attr:`documents_in_target_rate` above
    is comfortably 1. Renamed from ``convergence_rate``; do not reintroduce that name or
    print this ahead of the primary measure -- doing exactly that on this same field
    manufactured a "total failure" reading of a run that mostly succeeded (the third such
    naming trap this project has hit; see §13.2 and §13.3 for the first two, one of which
    reversed a design verdict).
    """

    unconverged_units: Stats = field(default_factory=Stats)
    """Distribution of ``len(unconverged_units)`` per run -- how many units, not
    whether any. A hint naming 1 of 5 units is a different UX problem from one naming 12
    of 38 (T6.7); ``mean``/``maximum`` here are what the shortfall hint actually shows a
    user, and are computed over every run, converged or not (unlike ``attempts_to_converge``
    below, an empty list is a real, countable zero, not an absence to filter out).
    """

    paragraph_target_share_before: Stats = field(default_factory=Stats)
    paragraph_target_share_after: Stats = field(default_factory=Stats)

    attempts_histogram: dict[int, int] = field(default_factory=dict)
    attempts_to_converge: Stats = field(default_factory=Stats)

    fidelity_failure_rate: float = 0.0
    missing_fact_rate: float = 0.0
    missing_facts_total: int = 0

    length_ratio: Stats = field(default_factory=Stats)
    wall_clock: Stats = field(default_factory=Stats)
    llm_calls: Stats = field(default_factory=Stats)
    llm_calls_total: int = 0

    @property
    def wall_clock_p50(self) -> float:
        return self.wall_clock.p50

    @property
    def wall_clock_p95(self) -> float:
        return self.wall_clock.p95


def attempts_histogram(results: Sequence[CaseRunResult]) -> dict[int, int]:
    """Attempts-to-converge distribution, ascending by attempt count.

    Only converged runs are counted: an unconverged run spent its attempts and converged
    on none of them, so folding it in would understate the cost of the ones that worked.

    >>> attempts_histogram([CaseRunResult(case_id="a", attempts=2),
    ...                     CaseRunResult(case_id="b", attempts=2),
    ...                     CaseRunResult(case_id="c", attempts=3, converged=False)])
    {2: 2}
    """
    counter = Counter(r.attempts for r in results if r.converged)
    return dict(sorted(counter.items()))


def aggregate(results: Sequence[CaseRunResult], label: str = "") -> AggregateMetrics:
    """Aggregate the §6 metrics over runs. Safe on an empty sequence.

    >>> aggregate([]).runs
    0
    >>> m = aggregate([CaseRunResult(case_id="a", score_before=-3.0, score_after=1.0,
    ...                              band_before="hard", band_after="easy")])
    >>> m.runs, m.score_delta.mean, m.band_shift.mean, m.documents_in_target_rate
    (1, 4.0, 2.0, 1.0)
    """
    if not results:
        return AggregateMetrics(label=label)

    total = len(results)
    converged = [r for r in results if r.converged]
    return AggregateMetrics(
        label=label,
        runs=total,
        cases=len({r.case_id for r in results}),
        errors=sum(1 for r in results if r.error is not None),
        score_before=summarize(_present(r.score_before for r in results)),
        score_after=summarize(_present(r.score_after for r in results)),
        score_delta=summarize(_present(r.score_delta for r in results)),
        band_shift=summarize(_present(band_shift(r.band_before, r.band_after) for r in results)),
        band_after_counts=dict(sorted(Counter(r.band_after for r in results if r.band_after).items())),
        cefr_shift=summarize(_present(cefr_shift(r.cefr_before, r.cefr_after) for r in results)),
        documents_in_target_rate=sum(1 for r in results if r.in_target) / total,
        all_units_converged_rate=len(converged) / total,
        unconverged_units=summarize(len(r.unconverged_units) for r in results),
        paragraph_target_share_before=summarize(_present(r.paragraph_target_share_before for r in results)),
        paragraph_target_share_after=summarize(_present(r.paragraph_target_share_after for r in results)),
        attempts_histogram=attempts_histogram(results),
        attempts_to_converge=summarize(r.attempts for r in converged),
        fidelity_failure_rate=sum(1 for r in results if not r.fidelity_ok) / total,
        missing_fact_rate=sum(1 for r in results if r.missing_facts) / total,
        missing_facts_total=sum(len(r.missing_facts) for r in results),
        length_ratio=summarize(_present(r.length_ratio for r in results)),
        wall_clock=summarize(r.wall_clock_seconds for r in results),
        llm_calls=summarize(r.llm_calls for r in results),
        llm_calls_total=sum(r.llm_calls for r in results),
    )


def split_by_mode(results: Sequence[CaseRunResult]) -> dict[SimplifyMode, list[CaseRunResult]]:
    """Partition runs into WHOLE and CHUNKED. Empty modes are omitted.

    >>> sorted(split_by_mode([CaseRunResult(case_id="a", mode="chunked")]))
    ['chunked']
    """
    buckets: dict[SimplifyMode, list[CaseRunResult]] = {}
    for result in results:
        buckets.setdefault(result.mode, []).append(result)
    return buckets


def aggregate_by_mode(results: Sequence[CaseRunResult]) -> dict[SimplifyMode, AggregateMetrics]:
    """The §6 aggregate, split by mode — the primary view of the report."""
    return {mode: aggregate(runs, label=mode.upper()) for mode, runs in split_by_mode(results).items()}


def aggregate_by_case(results: Sequence[CaseRunResult]) -> dict[str, AggregateMetrics]:
    """Per-case aggregate over that case's runs, in first-seen order."""
    buckets: dict[str, list[CaseRunResult]] = {}
    for result in results:
        buckets.setdefault(result.case_id, []).append(result)
    return {case_id: aggregate(runs, label=case_id) for case_id, runs in buckets.items()}
