"""Scoring: match advisor predictions against labeled eval cases.

Matching is greedy one-to-one: a prediction matches an expected violation when the
rule name matches (exactly, or via `alt_rule_names`) and the character spans overlap.
A second prediction hitting an already-matched expected violation counts as a
duplicate, not a false positive. Unmatched predictions and unmatched expectations are
additionally cross-checked by span overlap alone ("rule confusions"): the model found
the right text span but attributed the wrong rule.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

from text_mate_tools.advisor_eval.models import EvalCase, ExpectedViolation, PredictedViolation


def resolve_expected_span(case: EvalCase, expected: ExpectedViolation) -> tuple[int, int]:
    """Resolve an expected violation to its (start, end) character span in the case text.

    Raises ValueError if the requested occurrence of the source substring does not exist —
    that is an authoring error in the eval case, not a model error.
    """
    pos = -1
    for _ in range(expected.occurrence):
        pos = case.text.find(expected.source, pos + 1)
        if pos == -1:
            raise ValueError(
                f"Case '{case.id}': occurrence {expected.occurrence} of source "
                f"'{expected.source[:60]}' not found in text (rule: {expected.rule_name})"
            )
    return pos, pos + len(expected.source)


def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return min(a[1], b[1]) > max(a[0], b[0])


def _rule_matches(prediction: PredictedViolation, expected: ExpectedViolation) -> bool:
    return prediction.rule_name == expected.rule_name or prediction.rule_name in expected.alt_rule_names


@dataclass
class CaseScore:
    case_id: str
    matched_expected: set[int] = field(default_factory=set)
    """Indices into case.expected that were found."""
    false_positives: list[PredictedViolation] = field(default_factory=list)
    duplicates: int = 0
    rule_confusions: list[tuple[int, PredictedViolation]] = field(default_factory=list)
    """(expected index, prediction) pairs where the span was found but the rule name was wrong."""
    total_expected: int = 0

    @property
    def tp(self) -> int:
        return len(self.matched_expected)

    @property
    def fn(self) -> int:
        return self.total_expected - self.tp

    @property
    def fp(self) -> int:
        return len(self.false_positives)

    @property
    def recall(self) -> float:
        return self.tp / self.total_expected if self.total_expected else 1.0

    @property
    def precision(self) -> float:
        predicted = self.tp + self.fp
        return self.tp / predicted if predicted else 1.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0


def score_case(case: EvalCase, predictions: list[PredictedViolation]) -> CaseScore:
    """Score one advisor run against one eval case."""
    expected_spans = [resolve_expected_span(case, e) for e in case.expected]
    score = CaseScore(case_id=case.id, total_expected=len(case.expected))

    unmatched_predictions: list[PredictedViolation] = []
    for prediction in predictions:
        prediction_span = (prediction.start, prediction.end)
        matched_index: int | None = None
        duplicate = False
        for i, expected in enumerate(case.expected):
            if not _rule_matches(prediction, expected) or not _spans_overlap(prediction_span, expected_spans[i]):
                continue
            if i in score.matched_expected:
                duplicate = True
                continue
            matched_index = i
            break

        if matched_index is not None:
            score.matched_expected.add(matched_index)
        elif duplicate:
            score.duplicates += 1
        else:
            unmatched_predictions.append(prediction)

    # Lenient pass: span found, wrong rule cited.
    confused_expected: set[int] = set()
    for prediction in unmatched_predictions:
        prediction_span = (prediction.start, prediction.end)
        for i in range(len(case.expected)):
            if i in score.matched_expected or i in confused_expected:
                continue
            if _spans_overlap(prediction_span, expected_spans[i]):
                confused_expected.add(i)
                score.rule_confusions.append((i, prediction))
                break
        else:
            score.false_positives.append(prediction)

    return score


@dataclass
class MultiRunScore:
    """Scores for N runs of the advisor on the same case."""

    case_id: str
    runs: list[CaseScore]
    total_expected: int

    @property
    def union_matched(self) -> set[int]:
        matched: set[int] = set()
        for run in self.runs:
            matched |= run.matched_expected
        return matched

    @property
    def union_recall(self) -> float:
        return len(self.union_matched) / self.total_expected if self.total_expected else 1.0

    @property
    def mean_recall(self) -> float:
        return sum(run.recall for run in self.runs) / len(self.runs)

    @property
    def stability(self) -> float:
        """Mean pairwise Jaccard similarity of the matched-expected sets across runs.

        1.0 = every run finds the same violations; low values quantify the
        "run it again, find different things" effect. Defined as 1.0 for a single run.
        """
        if len(self.runs) < 2:
            return 1.0
        similarities: list[float] = []
        for a, b in combinations(self.runs, 2):
            union = a.matched_expected | b.matched_expected
            if not union:
                similarities.append(1.0)
            else:
                similarities.append(len(a.matched_expected & b.matched_expected) / len(union))
        return sum(similarities) / len(similarities)


def score_case_runs(case: EvalCase, runs: list[list[PredictedViolation]]) -> MultiRunScore:
    return MultiRunScore(
        case_id=case.id,
        runs=[score_case(case, predictions) for predictions in runs],
        total_expected=len(case.expected),
    )


@dataclass
class RuleAggregate:
    tp: int = 0
    fn: int = 0
    confusions: int = 0

    @property
    def recall(self) -> float:
        total = self.tp + self.fn
        return self.tp / total if total else 1.0


def aggregate_by_rule(cases: list[EvalCase], scores: list[CaseScore]) -> dict[str, RuleAggregate]:
    """Aggregate detection outcomes per rule across cases (uses the first run per case)."""
    per_rule: dict[str, RuleAggregate] = defaultdict(RuleAggregate)
    for case, score in zip(cases, scores, strict=True):
        confused = {i for i, _ in score.rule_confusions}
        for i, expected in enumerate(case.expected):
            if i in score.matched_expected:
                per_rule[expected.rule_name].tp += 1
            else:
                per_rule[expected.rule_name].fn += 1
                if i in confused:
                    per_rule[expected.rule_name].confusions += 1
    return dict(per_rule)
