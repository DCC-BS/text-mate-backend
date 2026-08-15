import json
from pathlib import Path

import pytest

from text_mate_tools.simplify_eval.corpus import coverage, load_cases, validate_cases
from text_mate_tools.simplify_eval.models import (
    CHUNKING_THRESHOLD_CHARS,
    CaseRunResult,
    SimplifyEvalCase,
    SimplifyOutput,
)
from text_mate_tools.simplify_eval.scoring import (
    BAND_ORDER,
    CEFR_ORDER,
    Stats,
    aggregate,
    aggregate_by_case,
    aggregate_by_mode,
    attempts_histogram,
    band_shift,
    cefr_shift,
    german_band,
    percentile,
    split_by_mode,
    summarize,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = REPO_ROOT / "evals" / "simplify" / "cases"


def run(**overrides: object) -> CaseRunResult:
    """A CaseRunResult with sane defaults; override only what the assertion is about."""
    defaults: dict[str, object] = {
        "case_id": "case-a",
        "mode": "whole",
        "source_chars": 100,
        "result_chars": 100,
        "score_before": -3.0,
        "score_after": 1.0,
        "band_before": "hard",
        "band_after": "easy",
        "cefr_before": "C1",
        "cefr_after": "A2",
        "paragraphs_total": 4,
        "paragraphs_scored": 4,
        "paragraphs_in_target_before": 1,
        "paragraphs_in_target_after": 3,
        "wall_clock_seconds": 1.0,
    }
    return CaseRunResult.model_validate(defaults | overrides)


class TestSimplifyEvalCase:
    def test_paragraphs_split_on_blank_lines(self) -> None:
        case = SimplifyEvalCase(id="a", source_text="Titel\n\nErster Satz.\n\n\n  Zweiter Satz.  ")
        assert case.paragraphs() == ["Titel", "Erster Satz.", "Zweiter Satz."]

    def test_char_count_and_default_language(self) -> None:
        case = SimplifyEvalCase(id="a", source_text="abcde")
        assert case.char_count == 5
        assert case.language == "de"

    def test_mode_at_threshold_boundary(self) -> None:
        exactly = SimplifyEvalCase(id="a", source_text="x" * CHUNKING_THRESHOLD_CHARS)
        over = SimplifyEvalCase(id="b", source_text="x" * (CHUNKING_THRESHOLD_CHARS + 1))
        assert exactly.expected_mode() == "whole"
        assert over.expected_mode() == "chunked"

    def test_threshold_is_overridable(self) -> None:
        case = SimplifyEvalCase(id="a", source_text="x" * 500)
        assert case.expected_mode(threshold=100) == "chunked"

    def test_score_and_band_are_optional(self) -> None:
        case = SimplifyEvalCase(id="a", source_text="Kurzer Text.")
        assert case.source_score is None
        assert case.source_band is None
        assert case.must_keep_facts == []


class TestSimplifyOutputDefaults:
    def test_defaults_describe_a_single_shot_rewrite(self) -> None:
        output = SimplifyOutput(text="neu")
        assert (output.attempts, output.llm_calls, output.fidelity_failures) == (1, 1, 0)
        assert output.mode is None
        assert output.unconverged_units == []


class TestCaseRunResultProperties:
    def test_score_delta(self) -> None:
        assert run().score_delta == 4.0

    def test_score_delta_none_when_unscored(self) -> None:
        assert run(score_after=None).score_delta is None

    def test_length_ratio(self) -> None:
        assert run(source_chars=200, result_chars=150).length_ratio == 0.75

    def test_length_ratio_none_on_empty_source(self) -> None:
        assert run(source_chars=0).length_ratio is None

    def test_in_target_follows_band_after(self) -> None:
        assert run(band_after="easy").in_target
        assert not run(band_after="ok").in_target

    def test_fidelity_ok_requires_gate_and_facts(self) -> None:
        assert run().fidelity_ok
        assert not run(fidelity_failures=1).fidelity_ok
        assert not run(missing_facts=["3. April 2026"]).fidelity_ok

    def test_paragraph_target_shares(self) -> None:
        result = run()
        assert result.paragraph_target_share_before == 0.25
        assert result.paragraph_target_share_after == 0.75

    def test_paragraph_share_none_when_nothing_scorable(self) -> None:
        assert run(paragraphs_scored=0).paragraph_target_share_after is None


class TestGermanBand:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [(4.0, "easy"), (0.0, "easy"), (-0.01, "ok"), (-2.0, "ok"), (-2.01, "hard"), (-9.9, "hard")],
    )
    def test_calibrated_thresholds(self, score: float, expected: str) -> None:
        assert german_band(score) == expected

    def test_easy_floor_matches_cefr_b1(self) -> None:
        # §2.1: CEFR in {A1, A2, B1} is exactly ZIX >= 0, which is exactly band "easy".
        assert german_band(0.0) == "easy"
        assert german_band(-0.0001) != "easy"


class TestShifts:
    def test_band_shift_is_signed_towards_easy(self) -> None:
        assert band_shift("hard", "easy") == 2
        assert band_shift("ok", "ok") == 0
        assert band_shift("easy", "hard") == -2

    def test_band_shift_none_when_missing(self) -> None:
        assert band_shift(None, "easy") is None
        assert band_shift("easy", None) is None

    def test_cefr_shift_is_signed_towards_a1(self) -> None:
        assert cefr_shift("C1", "A2") == 3
        assert cefr_shift("B1", "B1") == 0
        assert cefr_shift("A2", "C2") == -4

    def test_cefr_shift_none_for_languages_without_cefr(self) -> None:
        # fr/it have no CEFR mapping (§10) — absent by design, not by failure.
        assert cefr_shift(None, None) is None
        assert cefr_shift("C1", "unbekannt") is None

    def test_scales_are_ordered_easiest_last(self) -> None:
        assert BAND_ORDER["hard"] < BAND_ORDER["ok"] < BAND_ORDER["easy"]
        assert CEFR_ORDER["C2"] < CEFR_ORDER["B1"] < CEFR_ORDER["A1"]


class TestStats:
    def test_percentile_interpolates(self) -> None:
        assert percentile([1, 2, 3, 4], 0.5) == 2.5
        assert percentile([1, 2, 3, 4], 0.0) == 1.0
        assert percentile([1, 2, 3, 4], 1.0) == 4.0

    def test_percentile_single_and_empty(self) -> None:
        assert percentile([7.0], 0.95) == 7.0
        assert percentile([], 0.5) == 0.0

    def test_summarize(self) -> None:
        stats = summarize([1.0, 2.0, 3.0])
        assert stats.n == 3
        assert stats.mean == 2.0
        assert stats.p50 == 2.0
        assert (stats.minimum, stats.maximum) == (1.0, 3.0)
        assert stats.spread == pytest.approx(1.0)

    def test_summarize_single_value_has_zero_spread(self) -> None:
        assert summarize([5.0]).spread == 0.0

    def test_summarize_empty(self) -> None:
        assert summarize([]) == Stats()

    def test_format_mean(self) -> None:
        assert Stats().format_mean() == "--"
        assert summarize([1.0, 3.0]).format_mean() == "2.00 ± 1.41"


class TestAttemptsHistogram:
    def test_counts_only_converged_runs(self) -> None:
        results = [run(attempts=1), run(attempts=2), run(attempts=2), run(attempts=3, converged=False)]
        assert attempts_histogram(results) == {1: 1, 2: 2}

    def test_empty(self) -> None:
        assert attempts_histogram([]) == {}


class TestAggregate:
    def test_empty_is_safe(self) -> None:
        metrics = aggregate([], label="EMPTY")
        assert metrics.runs == 0
        assert metrics.label == "EMPTY"
        assert metrics.all_units_converged_rate == 0.0
        assert metrics.documents_in_target_rate == 0.0
        assert metrics.attempts_histogram == {}

    def test_score_and_band_shift(self) -> None:
        metrics = aggregate([run(), run(score_before=-1.0, score_after=0.0, band_before="ok")])
        assert metrics.runs == 2
        assert metrics.cases == 1
        assert metrics.score_before.mean == -2.0
        assert metrics.score_after.mean == 0.5
        assert metrics.score_delta.mean == 2.5
        assert metrics.band_shift.mean == 1.5
        assert metrics.band_after_counts == {"easy": 2}

    def test_cefr_shift_only_over_available_runs(self) -> None:
        metrics = aggregate([run(), run(cefr_before=None, cefr_after=None)])
        assert metrics.cefr_shift.n == 1
        assert metrics.cefr_shift.mean == 3.0

    def test_documents_in_target_is_the_band_after_criterion(self) -> None:
        """PRIMARY measure: whether the *assembled* text reached the target band --
        independent of whether every unit inside it converged (§14.1)."""
        metrics = aggregate([run(), run(converged=False, band_after="ok")])
        assert metrics.documents_in_target_rate == 0.5

    def test_all_units_converged_is_the_per_unit_gate_result(self) -> None:
        """SECONDARY measure: whether every unit reached target."""
        metrics = aggregate([run(unconverged_units=[]), run(unconverged_units=[1])])
        assert metrics.all_units_converged_rate == 0.5

    def test_the_two_rates_can_disagree_in_either_direction(self) -> None:
        """The real corpus shape (§13.6): every unit converges, but the assembled
        document's own score still misses the target band."""
        all_units_but_not_document = run(unconverged_units=[], band_after="ok")
        document_but_not_all_units = run(unconverged_units=[1], band_after="easy")
        metrics = aggregate([all_units_but_not_document, document_but_not_all_units])
        assert metrics.documents_in_target_rate == 0.5
        assert metrics.all_units_converged_rate == 0.5

    def test_unconverged_units_distribution(self) -> None:
        metrics = aggregate(
            [
                run(unconverged_units=[]),
                run(unconverged_units=[3]),
                run(unconverged_units=list(range(12))),
            ]
        )
        assert metrics.unconverged_units.mean == pytest.approx((0 + 1 + 12) / 3)
        assert metrics.unconverged_units.maximum == 12

    def test_paragraph_target_shares(self) -> None:
        metrics = aggregate([run()])
        assert metrics.paragraph_target_share_before.mean == 0.25
        assert metrics.paragraph_target_share_after.mean == 0.75

    def test_fidelity_failure_rate_covers_gate_and_facts(self) -> None:
        metrics = aggregate([run(), run(fidelity_failures=2), run(missing_facts=["a", "b"])])
        assert metrics.fidelity_failure_rate == pytest.approx(2 / 3)
        assert metrics.missing_fact_rate == pytest.approx(1 / 3)
        assert metrics.missing_facts_total == 2

    def test_length_ratio_and_llm_calls(self) -> None:
        metrics = aggregate([run(result_chars=50), run(result_chars=150)])
        assert metrics.length_ratio.mean == 1.0
        assert metrics.llm_calls_total == 2
        assert metrics.llm_calls.mean == 1.0

    def test_wall_clock_percentiles(self) -> None:
        metrics = aggregate([run(wall_clock_seconds=float(s)) for s in range(1, 21)])
        assert metrics.wall_clock_p50 == pytest.approx(10.5)
        assert metrics.wall_clock_p95 == pytest.approx(19.05)

    def test_errors_are_counted_not_dropped(self) -> None:
        metrics = aggregate([run(), run(error="TimeoutError: boom")])
        assert metrics.runs == 2
        assert metrics.errors == 1


class TestSplitByMode:
    def test_split(self) -> None:
        buckets = split_by_mode([run(mode="whole"), run(mode="chunked"), run(mode="whole")])
        assert sorted(buckets) == ["chunked", "whole"]
        assert len(buckets["whole"]) == 2

    def test_empty_modes_are_omitted(self) -> None:
        assert list(split_by_mode([run(mode="whole")])) == ["whole"]

    def test_aggregate_by_mode_keeps_modes_separate(self) -> None:
        results = [
            run(mode="whole", score_after=2.0),
            run(mode="chunked", case_id="case-b", score_after=-1.0, band_after="ok"),
        ]
        by_mode = aggregate_by_mode(results)
        assert by_mode["whole"].score_after.mean == 2.0
        assert by_mode["chunked"].score_after.mean == -1.0
        assert by_mode["whole"].label == "WHOLE"

    def test_aggregate_by_case_preserves_first_seen_order(self) -> None:
        results = [run(case_id="b"), run(case_id="a"), run(case_id="b")]
        by_case = aggregate_by_case(results)
        assert list(by_case) == ["b", "a"]
        assert by_case["b"].runs == 2


class TestCorpusLoading:
    def write(self, directory: Path, case: dict[str, object]) -> None:
        (directory / f"{case['id']}.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")

    def test_load_and_filter(self, tmp_path: Path) -> None:
        self.write(tmp_path, {"id": "a", "source_text": "Text A."})
        self.write(tmp_path, {"id": "b", "source_text": "Text B."})
        assert [c.id for c in load_cases(tmp_path)] == ["a", "b"]
        assert [c.id for c in load_cases(tmp_path, ["b"])] == ["b"]

    def test_empty_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No eval case files"):
            load_cases(tmp_path)

    def test_unknown_case_id_raises(self, tmp_path: Path) -> None:
        self.write(tmp_path, {"id": "a", "source_text": "Text A."})
        with pytest.raises(ValueError, match="Unknown case ids: zzz"):
            load_cases(tmp_path, ["zzz"])


class TestValidateCases:
    def test_valid_corpus_reports_nothing(self) -> None:
        case = SimplifyEvalCase(
            id="a",
            source_text="Die Frist läuft am 1. Juni 2026 ab.",
            source_score=-1.0,
            source_band="ok",
            must_keep_facts=["1. Juni 2026"],
        )
        assert validate_cases([case]) == []

    def test_duplicate_ids(self) -> None:
        cases = [SimplifyEvalCase(id="a", source_text="x"), SimplifyEvalCase(id="a", source_text="y")]
        assert any("Duplicate case id 'a'" in e for e in validate_cases(cases))

    def test_empty_source_text(self) -> None:
        assert any("source_text is empty" in e for e in validate_cases([SimplifyEvalCase(id="a", source_text="  ")]))

    def test_must_keep_fact_must_be_a_substring(self) -> None:
        case = SimplifyEvalCase(id="a", source_text="Kein Datum hier.", must_keep_facts=["1. Juni 2026"])
        errors = validate_cases([case])
        assert len(errors) == 1
        assert "must-keep fact '1. Juni 2026' is not a substring" in errors[0]

    def test_band_contradicting_score(self) -> None:
        case = SimplifyEvalCase(id="a", source_text="Text.", source_score=-5.0, source_band="easy")
        errors = validate_cases([case])
        assert len(errors) == 1
        assert "contradicts" in errors[0] and "expected 'hard'" in errors[0]

    def test_band_check_is_german_only(self) -> None:
        # LIX/Gulpease have different calibrations; german_band must not judge them (§10).
        case = SimplifyEvalCase(id="a", source_text="Texte.", language="fr", source_score=-5.0, source_band="easy")
        assert validate_cases([case]) == []


class TestCoverage:
    def test_counts_modes_languages_and_bands(self) -> None:
        cases = [
            SimplifyEvalCase(id="a", source_text="x" * 100, source_score=-3.0),
            SimplifyEvalCase(id="b", source_text="x" * 11000, source_score=1.0, must_keep_facts=[]),
        ]
        stats = coverage(cases)
        assert stats.cases == 2
        assert stats.modes == {"whole": 1, "chunked": 1}
        assert stats.bands == {"hard": 1, "easy": 1}
        assert stats.languages == {"de": 2}
        assert (stats.min_chars, stats.max_chars) == (100, 11000)

    def test_shortfalls_flag_a_thin_corpus(self) -> None:
        stats = coverage([SimplifyEvalCase(id="a", source_text="x" * 100, source_score=-3.0)])
        warnings = stats.shortfalls()
        assert any("asks for 20-30" in w for w in warnings)
        assert any("CHUNKED" in w for w in warnings)
        assert any("multiple source bands" in w for w in warnings)

    def test_no_shortfall_for_a_complete_corpus(self) -> None:
        # A "complete" corpus must satisfy every shortfall check, not just size: it needs
        # both modes, a spread of bands including `hard` (an all-easy corpus cannot separate
        # one shot from a loop), and cases that are verbatim published documents rather than
        # illustrations. Scores cycle -4.5/-1.0/0.5 to cover hard/ok/easy; -4.5 also sits
        # more than 3.2 ZIX below target, which is the measured reach of a single rewrite,
        # so at least one case can only be solved by retrying.
        cases = [
            SimplifyEvalCase(
                id=f"c{i}",
                source_text="x" * (100 if i else 11000),
                source_score=(-4.5, -1.0, 0.5)[i % 3],
                provenance="real",
                source_url=f"https://example.invalid/doc/{i}.pdf",
            )
            for i in range(20)
        ]
        assert coverage(cases).shortfalls() == []

    def test_scores_grouped_by_language_and_language_specific_gaps(self) -> None:
        cases = [
            SimplifyEvalCase(id="de_hard", language="de", source_text="x" * 100, source_score=-3.0),
            SimplifyEvalCase(id="de_easy", language="de", source_text="x" * 100, source_score=1.0),
            SimplifyEvalCase(id="fr_hard", language="fr", source_text="x" * 100, source_score=55.0),
            SimplifyEvalCase(id="fr_easy", language="fr", source_text="x" * 100, source_score=35.0),
            SimplifyEvalCase(id="it_hard", language="it", source_text="x" * 100, source_score=50.0),
            SimplifyEvalCase(id="it_easy", language="it", source_text="x" * 100, source_score=85.0),
        ]
        stats = coverage(cases)
        assert stats.scores == {
            "de": (-3.0, 1.0),
            "fr": (35.0, 55.0),
            "it": (50.0, 85.0),
        }
        assert stats.gap_to_target("de") == (0.0, 3.0)
        assert stats.gap_to_target("fr") == (0.0, 15.0)
        assert stats.gap_to_target("it") == (0.0, 30.0)
        assert stats.gap_to_target() == (0.0, 0.0, 0.0, 3.0, 15.0, 30.0)
        assert stats.beyond_single_pass(3.2, "de") == 0
        assert stats.beyond_single_pass(3.2, "fr") == 1
        assert stats.beyond_single_pass(3.2, "it") == 1
        assert stats.beyond_single_pass(3.2) == 2


class TestSeededCorpusOnDisk:
    """The corpus in evals/simplify/cases must stay loadable and self-consistent."""

    def test_loads_and_validates(self) -> None:
        cases = load_cases(CORPUS_DIR)
        assert cases, "seed corpus is empty"
        assert validate_cases(cases) == []

    def test_exercises_both_modes(self) -> None:
        modes = coverage(load_cases(CORPUS_DIR)).modes
        assert modes.get("whole"), "no case exercises WHOLE mode"
        assert modes.get("chunked"), "no case exercises CHUNKED mode — see evals/simplify/README.md"

    def test_case_ids_match_filenames(self) -> None:
        for path in sorted(CORPUS_DIR.glob("*.json")):
            assert SimplifyEvalCase.model_validate_json(path.read_text(encoding="utf-8")).id == path.stem
