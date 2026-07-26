import pytest

from text_mate_tools.advisor_eval.models import EvalCase, ExpectedViolation, PredictedViolation
from text_mate_tools.advisor_eval.scoring import (
    aggregate_by_rule,
    resolve_expected_span,
    score_case,
    score_case_runs,
)


def make_case() -> EvalCase:
    return EvalCase(
        id="test-case",
        collections=["bundeskanzlei"],
        text="Die Sitzung beginnt um 9:30 Uhr. Die zweite Sitzung beginnt um 9:30 Uhr am Dienstag.",
        expected=[
            ExpectedViolation(rule_name="Uhrzeit mit Punkt in der 24-Stunden-Zählung", source="9:30", occurrence=1),
            ExpectedViolation(rule_name="Uhrzeit mit Punkt in der 24-Stunden-Zählung", source="9:30", occurrence=2),
        ],
    )


def prediction(rule_name: str, start: int, end: int) -> PredictedViolation:
    return PredictedViolation(rule_name=rule_name, start=start, end=end)


class TestResolveExpectedSpan:
    def test_first_occurrence(self) -> None:
        case = make_case()
        start, end = resolve_expected_span(case, case.expected[0])
        assert case.text[start:end] == "9:30"
        assert start == case.text.find("9:30")

    def test_second_occurrence(self) -> None:
        case = make_case()
        start, end = resolve_expected_span(case, case.expected[1])
        assert case.text[start:end] == "9:30"
        assert start > case.text.find("9:30")

    def test_missing_occurrence_raises(self) -> None:
        case = make_case()
        bad = ExpectedViolation(rule_name="x", source="9:30", occurrence=3)
        with pytest.raises(ValueError, match="occurrence 3"):
            resolve_expected_span(case, bad)

    def test_missing_source_raises(self) -> None:
        case = make_case()
        bad = ExpectedViolation(rule_name="x", source="nicht im Text")
        with pytest.raises(ValueError):
            resolve_expected_span(case, bad)


class TestScoreCase:
    def test_perfect_match(self) -> None:
        case = make_case()
        first = case.text.find("9:30")
        second = case.text.find("9:30", first + 1)
        predictions = [
            prediction("Uhrzeit mit Punkt in der 24-Stunden-Zählung", first, first + 4),
            prediction("Uhrzeit mit Punkt in der 24-Stunden-Zählung", second, second + 4),
        ]
        score = score_case(case, predictions)
        assert score.tp == 2
        assert score.fn == 0
        assert score.fp == 0
        assert score.recall == 1.0
        assert score.precision == 1.0

    def test_partial_span_overlap_counts(self) -> None:
        case = make_case()
        first = case.text.find("9:30")
        # Prediction covers "9:30 Uhr" — wider than the labeled span, still overlaps.
        predictions = [prediction("Uhrzeit mit Punkt in der 24-Stunden-Zählung", first, first + 8)]
        score = score_case(case, predictions)
        assert score.tp == 1
        assert score.fn == 1

    def test_only_first_occurrence_found(self) -> None:
        case = make_case()
        first = case.text.find("9:30")
        predictions = [prediction("Uhrzeit mit Punkt in der 24-Stunden-Zählung", first, first + 4)]
        score = score_case(case, predictions)
        assert score.tp == 1
        assert score.fn == 1
        assert score.recall == 0.5

    def test_duplicate_prediction_not_false_positive(self) -> None:
        case = make_case()
        first = case.text.find("9:30")
        predictions = [
            prediction("Uhrzeit mit Punkt in der 24-Stunden-Zählung", first, first + 4),
            prediction("Uhrzeit mit Punkt in der 24-Stunden-Zählung", first, first + 4),
        ]
        score = score_case(case, predictions)
        assert score.tp == 1
        assert score.duplicates == 1
        assert score.fp == 0

    def test_wrong_rule_is_confusion_not_fp(self) -> None:
        case = make_case()
        first = case.text.find("9:30")
        predictions = [prediction("Volle Stunden ohne Minutenangabe", first, first + 4)]
        score = score_case(case, predictions)
        assert score.tp == 0
        assert len(score.rule_confusions) == 1
        assert score.fp == 0

    def test_alt_rule_name_matches(self) -> None:
        case = EvalCase(
            id="alt",
            collections=["merkblatt_behoerdenbriefe"],
            text="Ein sehr langer Schachtelsatz steht hier.",
            expected=[
                ExpectedViolation(
                    rule_name="Kurze, einfach gebaute Sätze",
                    source="Ein sehr langer Schachtelsatz steht hier.",
                    alt_rule_names=["Ein Gedanke pro Satz"],
                )
            ],
        )
        score = score_case(case, [prediction("Ein Gedanke pro Satz", 0, 41)])
        assert score.tp == 1

    def test_unrelated_prediction_is_fp(self) -> None:
        case = make_case()
        # "Dienstag" span — overlaps nothing labeled.
        pos = case.text.find("Dienstag")
        score = score_case(case, [prediction("Kein Amtsjargon", pos, pos + 8)])
        assert score.fp == 1
        assert score.rule_confusions == []

    def test_clean_case(self) -> None:
        case = EvalCase(id="clean", collections=["bundeskanzlei"], text="Alles gut.", expected=[])
        score = score_case(case, [])
        assert score.recall == 1.0
        assert score.precision == 1.0


class TestMultiRun:
    def test_union_recall_exceeds_single_run(self) -> None:
        case = make_case()
        first = case.text.find("9:30")
        second = case.text.find("9:30", first + 1)
        rule = "Uhrzeit mit Punkt in der 24-Stunden-Zählung"
        runs = [
            [prediction(rule, first, first + 4)],
            [prediction(rule, second, second + 4)],
        ]
        result = score_case_runs(case, runs)
        assert result.mean_recall == 0.5
        assert result.union_recall == 1.0
        assert result.stability == 0.0

    def test_stable_runs(self) -> None:
        case = make_case()
        first = case.text.find("9:30")
        rule = "Uhrzeit mit Punkt in der 24-Stunden-Zählung"
        runs = [[prediction(rule, first, first + 4)], [prediction(rule, first, first + 4)]]
        result = score_case_runs(case, runs)
        assert result.stability == 1.0

    def test_single_run_stability_is_one(self) -> None:
        case = make_case()
        result = score_case_runs(case, [[]])
        assert result.stability == 1.0


class TestAggregateByRule:
    def test_per_rule_counts(self) -> None:
        case = make_case()
        first = case.text.find("9:30")
        rule = "Uhrzeit mit Punkt in der 24-Stunden-Zählung"
        score = score_case(case, [prediction(rule, first, first + 4)])
        per_rule = aggregate_by_rule([case], [score])
        assert per_rule[rule].tp == 1
        assert per_rule[rule].fn == 1
        assert per_rule[rule].recall == 0.5
