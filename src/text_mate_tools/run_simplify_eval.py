"""
Run a simplifier against the eval corpus and report readability and fact-preservation metrics.

Measures, per case and aggregated **split by mode** (WHOLE / CHUNKED, docs/simplify_redesign.md
§4.1): score before/after with spread, band shift, CEFR shift, the **documents-in-target
rate** (primary -- did the assembled text a user gets back reach the target band), the
**all-units-converged rate** and unconverged-units distribution (secondary -- the §14.1
per-unit gate diagnostics that drive the shortfall hint, never a verdict on the run), share
of paragraphs reaching target, attempts-to-converge distribution, must-keep facts lost,
length ratio, wall-clock p50/p95 and LLM call count. See docs/simplify_redesign.md §6.

The two rate metrics answer different questions and are printed in that order on purpose:
a big CHUNKED document can have every unit converge while its assembled score still misses
target (rare), or -- the common real-corpus shape -- reach target as a document while one
of dozens of units stays short (§13.6). Reporting the per-unit number first, under a name
that read like the first, previously produced a "total failure" verdict on a run in which
12 of 16 documents were actually in target (§13.2 and §13.3 record the same trap twice
before this).

Fact preservation is measured **here and only here**. The pipeline has no runtime fidelity
gate: one was built and removed after it rejected nothing that was genuinely wrong while
doubling the call count. A false positive in this report costs a line a human reads; a
false positive in a gate costs a user their rewrite. Comparison is normalized on both
sides (``simplify_eval/normalize.py``) so the digit conversions the Bundeskanzlei rules
require are not reported as losses.

This runner depends on two narrow Protocols — ``Simplifier`` and ``Scorer`` in
``simplify_eval.models`` — and never on a concrete service. Five simplifiers ship with it,
and the two baselines answer different questions — see each entry:

    --simplifier main_single_shot   THE PRE-REDESIGN BASELINE: what shipped on `main`.
                                One LLM call for the whole document, `main`'s prompt
                                verbatim, no chunking, no scoring, no retry
                                (``simplify_eval/main_baseline.py``). Compare against
                                ``simplify`` to measure what the redesign as a whole
                                bought. Needs a live LLM.
    --simplifier simplify_single_shot   The ABLATION baseline. The Phase 4 pipeline with
                                ``simplify_max_attempts=1``: pass 1 only, no retry —
                                the new prompt and chunker, without the loop. Needs a
                                live LLM.
    --simplifier simplify       the full §14 pipeline: pass 1 plus exactly one retry
                                round per unit still outside the target band, fired
                                concurrently. Compare against simplify_single_shot to
                                isolate what the RETRY contributes from what the
                                rewritten PROMPT contributes. Needs a live LLM.
    --simplifier passthrough    returns the source unchanged; no LLM. Use it to smoke-test
                                the harness and to read the corpus's source-side numbers
                                (score_before, band, paragraphs in target).
    --simplifier none           validate the corpus and print coverage, then stop.

    --simplifier quick_action   RETIRED, and it fails with an explanation rather than a
                                confusing 400. It drove ``POST /quick-action`` with
                                ``plain_language``, which Phase 4 removed: the agent behind
                                it is now the loop's internal rewriter and the action is
                                deregistered (docs/simplify_redesign.md §3, "Old action").
                                The single-shot baseline it used to provide is
                                ``simplify_single_shot``, which measures the same shape of
                                run (one call, no retry) through the live pipeline.

Both ``simplify`` entries are the *same* ``SimplifyService`` class with different
constructor arguments, deliberately: a separate single-shot code path would measure the
fork rather than the loop.

Usage (from the repository root, so assets/ and evals/ resolve):

    # Corpus check only — no LLM, no scoring.
    uv run python -m text_mate_tools.run_simplify_eval --simplifier none

    # Source-side numbers only — no LLM, ZIX runs locally on CPU.
    uv run python -m text_mate_tools.run_simplify_eval --simplifier passthrough

    # What the redesign bought over `main`: the pre-redesign baseline, then the loop.
    uv run --env-file .env python -m text_mate_tools.run_simplify_eval --simplifier main_single_shot --json-out main.json --texts-out texts_main
    uv run --env-file .env python -m text_mate_tools.run_simplify_eval --simplifier simplify --json-out loop.json --texts-out texts_loop
    #   ... then blind the two text sets against each other for a human or LLM read:
    python -m text_mate_tools.simplify_eval.build_blind_pairs --left texts_main --left-name main_single_shot --right texts_loop --right-name simplify --out blind

    # What the RETRY alone buys: the ablation baseline, then the loop.
    # Both require a reachable vLLM endpoint.
    #   1. Point .env at the LLM:  LLM_API_KEY, LLM_URL, LLM_MODEL (plus AUTH_MODE,
    #      which Configuration.from_env requires; AUTH_MODE=none needs APP_MODE!=prod).
    #   2. From the repository root:
    uv run --env-file .env python -m text_mate_tools.run_simplify_eval --simplifier simplify_single_shot --runs 3 --json-out baseline.json
    uv run --env-file .env python -m text_mate_tools.run_simplify_eval --simplifier simplify --runs 3 --json-out loop.json
    #   3. Record both printed aggregates in docs/simplify_redesign.md. The difference
    #      between them is the retry's contribution; tune §14.5 knobs against it, not vibes.

Options:
    --cases DIR         Directory with eval case JSON files (default: evals/simplify/cases)
    --runs N            Runs per case (default: 1); metrics are meaned over runs
    --case-id ID        Only run the given case id(s); repeatable
    --simplifier NAME   simplify | simplify_single_shot | main_single_shot | passthrough
                        | none (default: passthrough)
    --threshold N       Chunking threshold in characters (default: 10000, §14.5)
    --json-out FILE     Also write the full per-run results as JSON
    --texts-out DIR     Also write each run's simplified text as <case_id>.run<N>.txt —
                        the input to a side-by-side read or an LLM judge

Environment:
    Same .env as the backend (LLM_API_KEY, LLM_URL, LLM_MODEL, AUTH_MODE, ...), and only
    for the two ``simplify`` simplifiers.
"""

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import final

from dcc_backend_common.logger import get_logger

from text_mate_backend.readability.languages.german import GermanAnalyzer
from text_mate_backend.services.simplify_service import SIMPLIFY_MAX_ATTEMPTS, SimplifyService
from text_mate_backend.services.text_analysis_service import TextAnalysisService
from text_mate_backend.utils.configuration import Configuration
from text_mate_tools.simplify_eval.corpus import (
    DEFAULT_CASES_DIR,
    TYPICAL_SINGLE_PASS_GAIN,
    coverage,
    load_cases,
    validate_cases,
)
from text_mate_tools.simplify_eval.models import (
    CHUNKING_THRESHOLD_CHARS,
    CaseRunResult,
    ReadabilityBand,
    Scorer,
    Simplifier,
    SimplifyEvalCase,
    SimplifyOutput,
)
from text_mate_tools.simplify_eval.normalize import missing_facts
from text_mate_tools.simplify_eval.scoring import (
    AggregateMetrics,
    aggregate,
    aggregate_by_case,
    aggregate_by_mode,
    band_shift,
    cefr_shift,
)

logger = get_logger("run_simplify_eval")

REPORT_WIDTH = 118
CASE_COLUMN_WIDTH = 34

CORPUS_CAVEAT = (
    "CAVEAT: the corpus is German. The harness is language-parameterised, but only German is\n"
    "        measured against real data; en/fr/it correctness rests on the ported readability\n"
    "        unit tests (docs/simplify_redesign.md §4.2 / §6), not on anything measured here."
)


@final
class GermanZixScorer:
    """ZIX-backed :class:`Scorer` — the same scorer the pipeline will gate on (§2.1, §4.3).

    Runs locally on CPU (spaCy + sklearn), so scoring the corpus needs no LLM. Wraps ZIX in
    try/except because it raises above 1M chars; the Phase 2 ``TextAnalysisService`` gets
    the same guard (T2.4).
    """

    score_label = "ZIX"
    min_words = 6

    def __init__(self) -> None:
        self._analyzer = GermanAnalyzer()

    async def score(self, text: str) -> float | None:
        return await asyncio.to_thread(self._analyzer.score, text)

    def band(self, score: float) -> ReadabilityBand:
        return self._analyzer.band(score)

    def cefr(self, score: float) -> str | None:
        return self._analyzer.cefr(score)


@final
class PassthroughSimplifier:
    """Returns the source unchanged — the do-nothing floor every simplifier must beat."""

    name = "passthrough"

    async def __call__(self, text: str, language: str) -> SimplifyOutput:
        return SimplifyOutput(text=text, attempts=1, llm_calls=0, converged=False)


@final
class SimplifyServiceSimplifier:
    """The Phase 4 pipeline (§4.1), in whichever configuration it was built with.

    Drives ``SimplifyService.simplify`` — the same orchestration ``POST /simplify``
    streams, minus the streaming — and translates its outcome into the harness's
    ``SimplifyOutput``. The translation is explicit rather than duck-typed because the
    backend cannot import ``SimplifyOutput`` (the package dependency runs the other way),
    so this adapter is the one place the two models are held level.

    ``converged``, ``attempts`` and ``llm_calls`` come from the service's own counters,
    so the two configurations below are directly comparable. ``fidelity_failures`` is
    left at its default: there is no runtime fidelity gate any more, and information
    loss is measured instead against each case's hand-listed ``must_keep_facts``.
    """

    def __init__(self, name: str, service: SimplifyService) -> None:
        self.name = name
        self.service = service

    async def __call__(self, text: str, language: str) -> SimplifyOutput:
        outcome = await self.service.simplify(text, language)
        return SimplifyOutput(
            text=outcome.text,
            attempts=outcome.attempts,
            llm_calls=outcome.llm_calls,
            converged=outcome.converged,
            mode=outcome.mode,
            unconverged_units=outcome.unconverged_units,
        )


QUICK_ACTION_RETIRED = (
    "--simplifier quick_action is retired. It drove POST /quick-action with "
    "'plain_language', which Phase 4 removed: that agent is now the simplify loop's "
    "internal rewriter and the quick action is deregistered "
    "(docs/simplify_redesign.md §3, 'Old action'). Use --simplifier simplify_single_shot "
    "for the single-shot baseline, or --simplifier simplify for the full loop."
)


def build_simplify_service(*, max_attempts: int, server_default_temperature: bool = False) -> SimplifyService:
    """Build the real service against the environment's LLM configuration."""
    config = Configuration.from_env()
    temperatures: dict[str, float | None] = (
        {"temperature_first": None, "temperature_retry": None} if server_default_temperature else {}
    )
    return SimplifyService(config, TextAnalysisService(), max_attempts=max_attempts, **temperatures)


def build_simplifier(name: str, *, server_default_temperature: bool = False) -> Simplifier | None:
    """Resolve the ``--simplifier`` argument. ``none`` yields ``None`` (corpus check only).

    ``server_default_temperature`` reaches only the two ``simplify`` entries. The
    baseline and ``passthrough`` have no temperature to drop: ``main`` never set one,
    which is the whole reason the flag exists.
    """
    if name == "none":
        return None
    if name == "passthrough":
        return PassthroughSimplifier()
    if name == "simplify":
        return SimplifyServiceSimplifier(
            name,
            build_simplify_service(
                max_attempts=SIMPLIFY_MAX_ATTEMPTS, server_default_temperature=server_default_temperature
            ),
        )
    if name == "main_single_shot":
        # The pre-redesign baseline. Imported lazily so a corpus check or a passthrough
        # run never has to construct an LLM configuration to reach it.
        from text_mate_tools.simplify_eval.main_baseline import MainSingleShotSimplifier

        return MainSingleShotSimplifier(Configuration.from_env())
    if name == "simplify_single_shot":
        # The baseline: one rewrite, no retry. Compared against `simplify`, the difference
        # is the loop; compared against `passthrough`, the difference is the rewrite. Both
        # comparisons need this to be the same code path as the real one.
        return SimplifyServiceSimplifier(
            name, build_simplify_service(max_attempts=1, server_default_temperature=server_default_temperature)
        )
    if name == "quick_action":
        raise ValueError(QUICK_ACTION_RETIRED)
    raise ValueError(f"Unknown simplifier '{name}'")


def split_paragraphs(text: str) -> list[str]:
    """Blank-line split, as ``useBaseEditor.ts`` produces and §4.1 Stage 0 consumes.

    The classifying, offset-preserving chunker is T2.5; the harness needs only the units.
    """
    return [p.strip() for p in text.split("\n\n") if p.strip()]


async def _count_in_target(scorer: Scorer, paragraphs: Sequence[str]) -> tuple[int, int]:
    """(paragraphs scored, paragraphs whose band is ``easy``)."""
    scored = 0
    in_target = 0
    for paragraph in paragraphs:
        score = await scorer.score(paragraph)
        if score is None:
            continue
        scored += 1
        if scorer.band(score) == "easy":
            in_target += 1
    return scored, in_target


async def run_case_once(
    case: SimplifyEvalCase,
    simplifier: Simplifier,
    scorer: Scorer,
    run_index: int,
    threshold: int = CHUNKING_THRESHOLD_CHARS,
) -> CaseRunResult:
    """Simplify one case once and score both sides of it.

    Scoring is done by the harness rather than trusted from the simplifier, so the
    baseline (which scores nothing) and the Phase 4 loop (which scores everything) are
    measured on the same instrument.
    """
    source_paragraphs = case.paragraphs()
    score_before = await scorer.score(case.source_text)
    scored_before, in_target_before = await _count_in_target(scorer, source_paragraphs)

    started = time.monotonic()
    error: str | None = None
    try:
        output = await simplifier(case.source_text, case.language)
    except Exception as exc:  # noqa: BLE001 - one failing case must not abort the corpus
        logger.exception("Simplifier failed", case_id=case.id, run_index=run_index)
        error = f"{type(exc).__name__}: {exc}"
        output = SimplifyOutput(text=case.source_text, attempts=1, llm_calls=0, converged=False)
    elapsed = time.monotonic() - started

    score_after = await scorer.score(output.text)
    result_paragraphs = split_paragraphs(output.text)
    scored_after, in_target_after = await _count_in_target(scorer, result_paragraphs)

    return CaseRunResult(
        case_id=case.id,
        run_index=run_index,
        mode=output.mode or case.expected_mode(threshold),
        language=case.language,
        score_label=scorer.score_label,
        source_chars=case.char_count,
        result_chars=len(output.text),
        score_before=score_before,
        score_after=score_after,
        band_before=scorer.band(score_before) if score_before is not None else None,
        band_after=scorer.band(score_after) if score_after is not None else None,
        cefr_before=scorer.cefr(score_before) if score_before is not None else None,
        cefr_after=scorer.cefr(score_after) if score_after is not None else None,
        paragraphs_total=len(source_paragraphs),
        # Share-of-target is reported against the source-side denominator so the before and
        # after shares are comparable even though 1-in-N-out changes the paragraph count.
        paragraphs_scored=max(scored_before, scored_after),
        paragraphs_in_target_before=in_target_before,
        paragraphs_in_target_after=in_target_after,
        attempts=output.attempts,
        converged=output.converged,
        unconverged_units=output.unconverged_units,
        fidelity_failures=output.fidelity_failures,
        # Normalized on both sides: a simplification legitimately turns "dreissig Tagen"
        # into "30 Tagen" and "40.50 Franken" into "Fr. 40.50", and an exact substring
        # test reports those as lost facts. See simplify_eval/normalize.py.
        missing_facts=missing_facts(case.must_keep_facts, output.text),
        llm_calls=output.llm_calls,
        wall_clock_seconds=elapsed,
        error=error,
        result_text=output.text,
    )


def _format_shift(value: int | None) -> str:
    return f"{value:+d}" if value is not None else "--"


def _format_score(value: float | None) -> str:
    return f"{value:6.2f}" if value is not None else "    --"


def print_case_table(results: Sequence[CaseRunResult], runs: int) -> None:
    """Per-case table: one row per case, meaned over its runs.

    ``inTgt`` is the PRIMARY measure -- did this case's *assembled* text reach the
    target band (``documents_in_target_rate``, docs/simplify_redesign.md §14.1) -- not
    the per-unit gate result. A large CHUNKED document can read 0 here while every one
    of its units individually converged (see the ``AGGREGATE`` section's
    ``all units converged`` line); do not conflate the two, that confusion previously
    produced a "total failure" reading of a run that mostly succeeded.
    """
    print(
        f"{'case':<{CASE_COLUMN_WIDTH}} {'mode':<8} {'chars':>6} {'before':>7} {'after':>7} "
        f"{'Δscore':>7} {'Δband':>6} {'ΔCEFR':>6} {'inTgt':>5} {'para':>9} {'len':>5} {'sec':>6}"
    )
    print("-" * REPORT_WIDTH)
    for case_id, metrics in aggregate_by_case(results).items():
        case_runs = [r for r in results if r.case_id == case_id]
        first = case_runs[0]
        cefr = metrics.cefr_shift
        para = metrics.paragraph_target_share_after
        print(
            f"{case_id:<{CASE_COLUMN_WIDTH}} {first.mode:<8} {first.source_chars:>6} "
            f"{metrics.score_before.mean:>7.2f} {metrics.score_after.mean:>7.2f} "
            f"{metrics.score_delta.mean:>+7.2f} {metrics.band_shift.mean:>+6.2f} "
            f"{(f'{cefr.mean:+.2f}' if cefr.n else '--'):>6} "
            f"{metrics.documents_in_target_rate:>5.2f} "
            f"{(f'{para.mean:.2f}' if para.n else '--'):>9} "
            f"{(f'{metrics.length_ratio.mean:.2f}' if metrics.length_ratio.n else '--'):>5} "
            f"{metrics.wall_clock.p50:>6.1f}"
        )
        if runs > 1:
            print(f"{'':<{CASE_COLUMN_WIDTH}} spread: score_after ±{metrics.score_after.spread:.2f}")
        for run in case_runs:
            if run.error:
                print(f"{'':<{CASE_COLUMN_WIDTH}} ERROR run {run.run_index + 1}: {run.error}")
            if run.missing_facts:
                print(f"{'':<{CASE_COLUMN_WIDTH}} lost facts run {run.run_index + 1}: {'; '.join(run.missing_facts)}")


def print_aggregate(metrics: AggregateMetrics) -> None:
    """The §6 metric block for one slice (a mode, or the whole corpus).

    ``documents in target`` leads the block on purpose: it is the PRIMARY success
    measure -- the share of runs whose assembled text is what a user would actually
    receive as "done" (docs/simplify_redesign.md §14.1/14.4). Everything below it,
    starting with ``all units converged``, is secondary: diagnostics of the per-unit
    gate that drives the ``unconverged_units`` shortfall hint, not a second verdict
    on the run. The two can and do disagree on real CHUNKED documents (§13.6) -- printing
    the per-unit number first, under a name that sounded like the first, is exactly what
    previously produced a "total failure" reading of a run that mostly succeeded.
    """
    if not metrics.runs:
        return
    print(f"\n  {metrics.label}  ({metrics.cases} case(s), {metrics.runs} run(s))")
    print(f"    score before          {metrics.score_before.format_mean()}")
    print(f"    score after           {metrics.score_after.format_mean()}")
    print(f"    score shift           {metrics.score_delta.format_mean()}")
    print(f"    band shift            {metrics.band_shift.format_mean()}   after: {metrics.band_after_counts or '--'}")
    print(
        f"    CEFR shift            {metrics.cefr_shift.format_mean()}   (levels towards A1; n={metrics.cefr_shift.n})"
    )
    print(
        f"    documents in target    {metrics.documents_in_target_rate:.2f}"
        "   <- PRIMARY: assembled text reached the target band (the badge the user sees)"
    )
    print(
        f"    all units converged   {metrics.all_units_converged_rate:.2f}"
        "   secondary: every unit reached target (drives the shortfall hint, not a verdict)"
    )
    print(
        f"    unconverged units      mean {metrics.unconverged_units.mean:.1f}, "
        f"max {metrics.unconverged_units.maximum:.0f} per document"
        "   (what the shortfall hint would name, T6.7)"
    )
    print(
        f"    paragraphs in target  {metrics.paragraph_target_share_before.mean:.2f}"
        f" -> {metrics.paragraph_target_share_after.mean:.2f}"
    )
    print(
        f"    attempts to converge  {metrics.attempts_to_converge.format_mean(1)}"
        f"   histogram {metrics.attempts_histogram or '--'}"
    )
    # Fact preservation is an observation, never a gate: nothing in the request path
    # checks it. Comparison is normalized (simplify_eval/normalize.py), so a legitimate
    # "dreissig Tagen" -> "30 Tagen" is not reported as a loss.
    print(
        f"    must-keep facts lost  {metrics.missing_fact_rate:.2f} of runs,"
        f" {metrics.missing_facts_total} fact(s) total"
    )
    print(f"    length ratio          {metrics.length_ratio.format_mean()}")
    print(f"    wall clock            p50 {metrics.wall_clock.p50:.1f}s   p95 {metrics.wall_clock.p95:.1f}s")
    print(f"    LLM calls             {metrics.llm_calls.format_mean(1)} per run, {metrics.llm_calls_total} total")
    if metrics.errors:
        print(f"    ERRORS                {metrics.errors} run(s) raised")


def print_report(results: Sequence[CaseRunResult], runs: int, simplifier_name: str) -> None:
    print("=" * REPORT_WIDTH)
    print(" SIMPLIFY EVAL REPORT")
    print("=" * REPORT_WIDTH)
    print(f" simplifier: {simplifier_name}    runs per case: {runs}")
    print(CORPUS_CAVEAT)
    print("=" * REPORT_WIDTH)

    print_case_table(results, runs)

    print("\n" + "-" * REPORT_WIDTH)
    print(" AGGREGATE, SPLIT BY MODE")
    print("-" * REPORT_WIDTH)
    by_mode = aggregate_by_mode(results)
    for mode in ("whole", "chunked"):
        if mode in by_mode:
            print_aggregate(by_mode[mode])
        else:
            print(f"\n  {mode.upper()}  — no case in this mode; the corpus does not exercise it")
    print_aggregate(aggregate(results, label="ALL MODES"))


def print_coverage(cases: Sequence[SimplifyEvalCase], threshold: int) -> None:
    """What the corpus spans — printed before any measurement, because it bounds all of it.

    The score distribution is the part that decides whether the eval can discriminate at
    all: if every case sits within one rewrite pass of the target band, every
    configuration scores perfectly and no knob can be tuned against the numbers.
    """
    stats = coverage(cases, threshold)
    print(
        f"Corpus: {stats.cases} case(s), {stats.min_chars}-{stats.max_chars} chars, "
        f"languages {stats.languages}, modes {stats.modes}, provenance {stats.provenance}"
    )
    gaps = stats.gap_to_target()
    if stats.scores:
        beyond = stats.beyond_single_pass(TYPICAL_SINGLE_PASS_GAIN)
        print(
            f"  source bands {stats.bands}   score {stats.scores[0]:+.2f} .. {stats.scores[-1]:+.2f}"
            f"   gap to target {gaps[0]:.2f} .. {gaps[-1]:.2f}"
        )
        print(
            f"  {beyond}/{len(stats.scores)} case(s) sit further than {TYPICAL_SINGLE_PASS_GAIN:.1f} ZIX below "
            f"target — only these can separate a single shot from the loop"
        )
    print(f"  {stats.with_must_keep_facts} case(s) carry must-keep facts, {stats.unreviewed_facts} unreviewed")
    for warning in stats.shortfalls():
        print(f"  WARNING: {warning}")


def build_json_output(results: Sequence[CaseRunResult], simplifier_name: str, runs: int) -> dict[str, object]:
    by_mode = aggregate_by_mode(results)
    return {
        "simplifier": simplifier_name,
        "runs": runs,
        "caveat": CORPUS_CAVEAT,
        "results": [result.model_dump() for result in results],
        "aggregate_by_mode": {
            mode: {
                "runs": metrics.runs,
                "cases": metrics.cases,
                "score_before_mean": metrics.score_before.mean,
                "score_after_mean": metrics.score_after.mean,
                "score_after_spread": metrics.score_after.spread,
                "score_delta_mean": metrics.score_delta.mean,
                "band_shift_mean": metrics.band_shift.mean,
                "band_after_counts": metrics.band_after_counts,
                "cefr_shift_mean": metrics.cefr_shift.mean,
                # PRIMARY: share of runs whose assembled text reached the target band --
                # what the user experiences. Lead with this field, not the one below.
                "documents_in_target_rate": metrics.documents_in_target_rate,
                # SECONDARY / diagnostic: share of runs where every unit converged
                # (§14.1's per-unit gate). Drives the shortfall hint, is not a verdict.
                "all_units_converged_rate": metrics.all_units_converged_rate,
                "unconverged_units_mean": metrics.unconverged_units.mean,
                "unconverged_units_max": metrics.unconverged_units.maximum,
                "paragraph_target_share_after_mean": metrics.paragraph_target_share_after.mean,
                "attempts_histogram": metrics.attempts_histogram,
                "missing_fact_rate": metrics.missing_fact_rate,
                "missing_facts_total": metrics.missing_facts_total,
                "length_ratio_mean": metrics.length_ratio.mean,
                "wall_clock_p50": metrics.wall_clock_p50,
                "wall_clock_p95": metrics.wall_clock_p95,
                "llm_calls_total": metrics.llm_calls_total,
                "errors": metrics.errors,
            }
            for mode, metrics in by_mode.items()
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the simplify eval harness.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_DIR)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--case-id", action="append", default=[])
    # quick_action stays a valid choice so it fails with QUICK_ACTION_RETIRED — an
    # argparse "invalid choice" would not explain where the baseline went.
    parser.add_argument(
        "--simplifier",
        choices=["simplify", "simplify_single_shot", "main_single_shot", "passthrough", "none", "quick_action"],
        default="passthrough",
    )
    parser.add_argument("--threshold", type=int, default=CHUNKING_THRESHOLD_CHARS)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument(
        "--texts-out",
        type=Path,
        default=None,
        help="Directory to write each run's simplified text to, as <case_id>.run<N>.txt. "
        "What a side-by-side reading, or an LLM judge, is given.",
    )
    parser.add_argument(
        "--server-default-temperature",
        action="store_true",
        help="Send no temperature at all, instead of the pipeline's 0.0/0.4 schedule. "
        "Use it when comparing against main_single_shot, which sets none either — "
        "otherwise the loop is the only side running deterministically and 'the loop' "
        "is confounded with 'no sampling'. Ignored by the non-simplify simplifiers.",
    )
    args = parser.parse_args()

    try:
        cases = load_cases(args.cases, args.case_id)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    errors = validate_cases(cases)
    if errors:
        raise SystemExit("Eval case validation failed:\n  " + "\n  ".join(errors))

    print_coverage(cases, args.threshold)

    try:
        simplifier = build_simplifier(args.simplifier, server_default_temperature=args.server_default_temperature)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if simplifier is None:
        print("Corpus is valid. Pass --simplifier passthrough, simplify_single_shot or simplify to measure.")
        return

    scorer = GermanZixScorer()
    # The label, not `simplifier.name`, is what the report and the JSON record: a saved
    # run that does not say which temperature regime produced it cannot be compared
    # against anything later.
    label = simplifier.name + (
        " + server-default temperature"
        if args.server_default_temperature and simplifier.name.startswith("simplify")
        else ""
    )
    print(f"Running {len(cases)} case(s) × {args.runs} run(s) through '{label}'")

    if args.texts_out:
        args.texts_out.mkdir(parents=True, exist_ok=True)

    results: list[CaseRunResult] = []
    for case in cases:
        for run_index in range(args.runs):
            result = await run_case_once(case, simplifier, scorer, run_index, args.threshold)
            results.append(result)
            if args.texts_out:
                # Written per run rather than at the end, so an interrupted run still
                # leaves behind everything it had already produced.
                (args.texts_out / f"{case.id}.run{run_index + 1}.txt").write_text(result.result_text, encoding="utf-8")
            print(
                f"  {case.id} run {run_index + 1}/{args.runs}: "
                f"{_format_score(result.score_before)} -> {_format_score(result.score_after)} "
                f"({result.cefr_before or '--'} -> {result.cefr_after or '--'}, "
                f"Δband {_format_shift(band_shift(result.band_before, result.band_after))}, "
                f"ΔCEFR {_format_shift(cefr_shift(result.cefr_before, result.cefr_after))}) "
                f"in {result.wall_clock_seconds:.1f}s"
            )

    print_report(results, args.runs, label)

    if args.json_out:
        args.json_out.write_text(
            json.dumps(build_json_output(results, label, args.runs), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON results written to {args.json_out}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
