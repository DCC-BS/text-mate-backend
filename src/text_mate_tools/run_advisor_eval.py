"""
Run the advisor against labeled eval cases and report detection metrics.

Measures per-rule and overall recall/precision, rule confusions (right span, wrong
rule), and — with --runs N — the gap between single-run recall and union recall across
runs, which quantifies the "run it again, find more" effect. See
docs/advisor_redesign.md §6.

Usage (from the repository root, so assets/docs/rules resolves):
    uv run --env-file .env src/text_mate_tools/run_advisor_eval.py [options]

Options:
    --cases DIR        Directory with eval case JSON files (default: evals/advisor/cases)
    --runs N           Runs per case for stability/union analysis (default: 1)
    --case-id ID       Only run the given case id(s); repeatable
    --json-out FILE    Also write the full results as JSON

Environment:
    Same .env as the backend (LLM_API_KEY, LLM_URL, LLM_MODEL, ...).
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.utils.configuration import Configuration
from text_mate_tools.advisor_eval.models import EvalCase, PredictedViolation
from text_mate_tools.advisor_eval.scoring import (
    MultiRunScore,
    aggregate_by_rule,
    resolve_expected_span,
    score_case_runs,
)

DEFAULT_CASES_DIR = Path("evals/advisor/cases")


def load_cases(directory: Path, case_ids: list[str]) -> list[EvalCase]:
    files = sorted(directory.glob("*.json"))
    if not files:
        raise SystemExit(f"No eval case files found in {directory}")
    cases = [EvalCase.model_validate_json(f.read_text()) for f in files]
    if case_ids:
        cases = [c for c in cases if c.id in case_ids]
        missing = set(case_ids) - {c.id for c in cases}
        if missing:
            raise SystemExit(f"Unknown case ids: {', '.join(sorted(missing))}")
    return cases


def validate_cases(cases: list[EvalCase], service: AdvisorService) -> None:
    """Fail fast on authoring errors: unknown rule names or unresolvable sources."""
    errors: list[str] = []
    for case in cases:
        known_rules = {rule.name for rule in service.filter_rules(set(case.collections))}
        if not known_rules:
            errors.append(f"Case '{case.id}': no rules found for collections {case.collections}")
            continue
        for expected in case.expected:
            for name in [expected.rule_name, *expected.alt_rule_names]:
                if name not in known_rules:
                    errors.append(f"Case '{case.id}': unknown rule name '{name}'")
            try:
                resolve_expected_span(case, expected)
            except ValueError as e:
                errors.append(str(e))
    if errors:
        raise SystemExit("Eval case validation failed:\n  " + "\n  ".join(errors))


def _utf16_to_codepoint_offset(text: str, utf16_offset: int) -> int:
    """Inverse of utils.text_offsets.to_utf16_offset.

    check_text_stream emits ranges in JavaScript UTF-16 code units (see
    advisor._build_violation_result), but the evaluator works in Python code
    points (resolve_expected_span uses str.find / len). This maps a UTF-16
    code-unit index back to a code-point index so predictions share the same
    offset basis as the expected spans. The two agree for all BMP characters
    and diverge only for code points >= U+10000 (surrogate pairs).
    """
    codepoint = 0
    units = 0
    for ch in text:
        if units >= utf16_offset:
            break
        units += 2 if ord(ch) >= 0x10000 else 1
        codepoint += 1
    return codepoint


async def run_case_once(service: AdvisorService, case: EvalCase) -> list[PredictedViolation]:
    predictions: list[PredictedViolation] = []
    async for container in service.check_text_stream(case.text, set(case.collections)):
        for violation in container.violations:
            predictions.append(
                PredictedViolation(
                    rule_name=violation.rule_name,
                    start=_utf16_to_codepoint_offset(case.text, violation.range.start),
                    end=_utf16_to_codepoint_offset(case.text, violation.range.end),
                    source=violation.source,
                )
            )
    return predictions


def print_report(cases: list[EvalCase], results: list[MultiRunScore], runs: int) -> None:
    print("=" * 88)
    print(" ADVISOR EVAL REPORT")
    print("=" * 88)

    header = f"{'case':<28} {'exp':>4} {'tp':>4} {'fn':>4} {'fp':>4} {'conf':>5} {'recall':>7} {'prec':>6}"
    if runs > 1:
        header += f" {'∪recall':>8} {'stable':>7}"
    print(header)
    print("-" * 88)

    for result in results:
        first = result.runs[0]
        mean_recall = result.mean_recall
        line = (
            f"{result.case_id:<28} {result.total_expected:>4} {first.tp:>4} {first.fn:>4} "
            f"{first.fp:>4} {len(first.rule_confusions):>5} {mean_recall:>7.2f} {first.precision:>6.2f}"
        )
        if runs > 1:
            line += f" {result.union_recall:>8.2f} {result.stability:>7.2f}"
        print(line)

    total_expected = sum(r.total_expected for r in results)
    total_tp = sum(r.runs[0].tp for r in results)
    total_fp = sum(r.runs[0].fp for r in results)
    overall_recall = total_tp / total_expected if total_expected else 1.0
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 1.0
    print("-" * 88)
    print(
        f"{'OVERALL (first run)':<28} {total_expected:>4} {total_tp:>4} "
        f"{total_expected - total_tp:>4} {total_fp:>4} {'':>5} {overall_recall:>7.2f} {overall_precision:>6.2f}"
    )

    if runs > 1:
        union_tp = sum(len(r.union_matched) for r in results)
        union_recall = union_tp / total_expected if total_expected else 1.0
        mean_stability = sum(r.stability for r in results) / len(results)
        print(f"\n  Mean single-run recall: {sum(r.mean_recall for r in results) / len(results):.2f}")
        print(
            f"  Union recall over {runs} runs: {union_recall:.2f}"
            f"  (gap = ensemble headroom: {union_recall - overall_recall:+.2f})"
        )
        print(f"  Mean stability (Jaccard): {mean_stability:.2f}")

    per_rule = aggregate_by_rule(cases, [r.runs[0] for r in results])
    missed = sorted(
        ((name, agg) for name, agg in per_rule.items() if agg.fn > 0),
        key=lambda item: item[1].recall,
    )
    if missed:
        print("\n  Rules with misses (first run):")
        for name, agg in missed:
            confusion_note = f", {agg.confusions} confused" if agg.confusions else ""
            print(f"    {name:<60} recall {agg.recall:.2f} ({agg.tp}/{agg.tp + agg.fn}{confusion_note})")


def build_json_output(results: list[MultiRunScore]) -> dict[str, object]:
    return {
        "cases": [
            {
                "case_id": result.case_id,
                "total_expected": result.total_expected,
                "union_recall": result.union_recall,
                "mean_recall": result.mean_recall,
                "stability": result.stability,
                "runs": [
                    {
                        "tp": run.tp,
                        "fn": run.fn,
                        "fp": run.fp,
                        "duplicates": run.duplicates,
                        "rule_confusions": len(run.rule_confusions),
                        "recall": run.recall,
                        "precision": run.precision,
                        "false_positives": [fp.model_dump() for fp in run.false_positives],
                    }
                    for run in result.runs
                ],
            }
            for result in results
        ]
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the advisor eval harness.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_DIR)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    config = Configuration.from_env()
    service = AdvisorService(config)

    cases = load_cases(args.cases, args.case_id)
    validate_cases(cases, service)
    print(f"Running {len(cases)} case(s) × {args.runs} run(s) against model {config.llm_model}")

    results: list[MultiRunScore] = []
    for case in cases:
        runs: list[list[PredictedViolation]] = []
        for run_index in range(args.runs):
            started = time.monotonic()
            predictions = await run_case_once(service, case)
            elapsed = time.monotonic() - started
            print(f"  {case.id} run {run_index + 1}/{args.runs}: {len(predictions)} findings in {elapsed:.1f}s")
            runs.append(predictions)
        results.append(score_case_runs(case, runs))

    print_report(cases, results, args.runs)

    if args.json_out:
        args.json_out.write_text(json.dumps(build_json_output(results), ensure_ascii=False, indent=2))
        print(f"\nJSON results written to {args.json_out}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
