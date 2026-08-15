"""Test vectors ported from blokkli's ``builtin.spec.ts``.

Every expectation of
``blokkli/editor/src/modules/readability/runtime/analyzers/builtin.spec.ts``
(MIT) is reproduced here, so the Python port is provably faithful. Where an
expectation could not be carried over verbatim it is documented at the test:

* German: blokkli scores German with the Wiener Sachtextformel, which we
  deliberately do not port (German uses ZIX). The German band/impact vectors are
  therefore re-expressed against the ZIX calibration, keeping the *shape* of the
  original assertions (below/at/above each band edge).
* English absolute FRE values: blokkli counts syllables with the npm
  ``syllable`` package, we use ``pyphen`` hyphenation, so exact numbers cannot
  match. The spec only asserts "is a number" / "is in the easy band" for
  English, and both are reproduced.
"""

import math

import pytest

from text_mate_backend.readability import build_score, get_analyzer
from text_mate_backend.readability.languages.english import EnglishAnalyzer, flesch_to_cefr
from text_mate_backend.readability.languages.french import FrenchAnalyzer
from text_mate_backend.readability.languages.german import GermanAnalyzer
from text_mate_backend.readability.languages.italian import ItalianAnalyzer

EN_LONG = (
    "The quick brown fox jumps over the lazy dog several times today "
    "while the sun shines brightly above the green hills."
)
EN_LONG_2 = (
    "Another sentence that is long enough to be analyzed by the readability tool "
    "and contains many words for testing purposes."
)
EN_COMPLEX = (
    "Complex governmental regulations frequently necessitate extraordinary administrative "
    "oversight mechanisms that substantially increase bureaucratic operational expenditures."
)
EN_PLAIN = "The cat sat on the mat. The dog ran to the park. The sun was bright and warm. The kids played in the yard."
IT_COMPLEX = (
    "Le complesse normative governative necessitano frequentemente di straordinari "
    "meccanismi di supervisione amministrativa."
)
FR_COMPLEX = (
    "Les réglementations gouvernementales complexes nécessitent fréquemment des "
    "mécanismes de surveillance administrative extraordinaires."
)
DE_PLAIN = (
    "Die Katze sitzt auf der Matte. Der Hund rennt in den Park. "
    "Die Sonne scheint hell und warm. Die Kinder spielen im Garten."
)


@pytest.fixture(scope="module")
def english() -> EnglishAnalyzer:
    return EnglishAnalyzer()


@pytest.fixture(scope="module")
def french() -> FrenchAnalyzer:
    return FrenchAnalyzer()


@pytest.fixture(scope="module")
def italian() -> ItalianAnalyzer:
    return ItalianAnalyzer()


@pytest.fixture(scope="module")
def german() -> GermanAnalyzer:
    return GermanAnalyzer()


class TestScore:
    """Scoring behaviour tests."""

    def test_returns_a_score_for_a_sufficiently_long_text(self, english: EnglishAnalyzer) -> None:
        score = english.score(EN_LONG)
        assert score is not None
        assert math.isfinite(score)

    def test_returns_none_for_text_shorter_than_min_words(self, english: EnglishAnalyzer) -> None:
        assert english.score("Too short.") is None

    def test_returns_none_for_empty_text(self, english: EnglishAnalyzer) -> None:
        assert english.score("") is None
        assert english.score("   \n  ") is None

    def test_unsupported_language_has_no_analyzer(self) -> None:
        """blokkli returns null per text for an unsupported langcode.

        Here the same is expressed one level up: an unsupported language has no
        analyzer at all, so the caller skips scoring instead of scoring badly.
        """
        assert get_analyzer("zh") is None
        assert get_analyzer("es") is None

    def test_handles_batch_of_multiple_texts(self, english: EnglishAnalyzer) -> None:
        results = [english.score(text) for text in (EN_LONG, "Short.", EN_LONG_2)]
        assert results[0] is not None
        assert results[1] is None  # too short
        assert results[2] is not None

    def test_produces_a_flesch_reading_ease_score_for_english(self, english: EnglishAnalyzer) -> None:
        score = english.score(EN_COMPLEX)
        assert score is not None
        assert math.isfinite(score)

    def test_produces_a_gulpease_score_for_italian(self, italian: ItalianAnalyzer) -> None:
        score = italian.score(IT_COMPLEX)
        assert score is not None
        assert score == pytest.approx(23.2)

    def test_produces_a_lix_score_for_french(self, french: FrenchAnalyzer) -> None:
        score = french.score(FR_COMPLEX)
        assert score is not None
        assert score == pytest.approx(87.0)

    def test_produces_a_zix_score_for_german(self, german: GermanAnalyzer) -> None:
        """blokkli asserts a WSTF number here; ZIX replaces it."""
        score = german.score(
            "Die komplexen Verwaltungsvorschriften erfordern häufig ausserordentliche "
            "Aufsichtsmechanismen, die den bürokratischen Aufwand erheblich steigern."
        )
        assert score is not None
        assert -10.0 <= score <= 10.0

    def test_classifies_a_plain_english_text_in_the_easy_fre_band(self, english: EnglishAnalyzer) -> None:
        score = english.score(EN_PLAIN)
        assert score is not None
        assert english.band(score) == "easy"

    def test_classifies_a_simple_german_text_in_the_easy_band(self, german: GermanAnalyzer) -> None:
        score = german.score(DE_PLAIN)
        assert score is not None
        assert german.band(score) == "easy"
        assert german.cefr(score) in {"A1", "A2", "B1"}


class TestScoreLabel:
    """Score label tests."""

    def test_returns_cefr_for_english(self, english: EnglishAnalyzer) -> None:
        assert english.score_label == "CEFR"

    def test_returns_gulpease_for_italian(self, italian: ItalianAnalyzer) -> None:
        assert italian.score_label == "Gulpease"

    def test_returns_lix_for_french(self, french: FrenchAnalyzer) -> None:
        assert french.score_label == "LIX"

    def test_returns_zix_for_german(self, german: GermanAnalyzer) -> None:
        """blokkli returns 'WSTF' here; German is scored with ZIX instead."""
        assert german.score_label == "ZIX"


class TestClassifyBand:
    """Band classification tests."""

    def test_classifies_high_fre_as_easy(self, english: EnglishAnalyzer) -> None:
        assert english.band(75) == "easy"

    def test_classifies_medium_fre_as_ok(self, english: EnglishAnalyzer) -> None:
        assert english.band(55) == "ok"

    def test_classifies_low_fre_as_hard(self, english: EnglishAnalyzer) -> None:
        assert english.band(45) == "hard"
        assert english.band(20) == "hard"

    def test_uses_gulpease_thresholds_for_italian(self, italian: ItalianAnalyzer) -> None:
        assert italian.band(85) == "easy"
        assert italian.band(70) == "ok"
        assert italian.band(50) == "hard"

    def test_uses_lix_thresholds_for_french(self, french: FrenchAnalyzer) -> None:
        assert french.band(30) == "easy"
        assert french.band(50) == "ok"
        assert french.band(65) == "hard"

    def test_uses_zix_thresholds_for_german(self, german: GermanAnalyzer) -> None:
        """Same shape as blokkli's WSTF band vectors, on the ZIX scale.

        easy <=> ZIX >= 0 <=> CEFR A1/A2/B1, which is the Einfache Sprache
        target; ok down to -2 (B2); hard below that.
        """
        assert german.band(5) == "easy"
        assert german.band(0.5) == "easy"
        assert german.band(0) == "easy"
        assert german.band(-0.1) == "ok"
        assert german.band(-2) == "ok"
        assert german.band(-2.1) == "hard"


class TestImpactForScore:
    """Impact level tests."""

    def test_returns_critical_for_fre_below_10(self, english: EnglishAnalyzer) -> None:
        assert english.impact(5) == "critical"

    def test_returns_serious_for_fre_below_25(self, english: EnglishAnalyzer) -> None:
        assert english.impact(20) == "serious"

    def test_returns_moderate_for_fre_below_40(self, english: EnglishAnalyzer) -> None:
        assert english.impact(35) == "moderate"

    def test_returns_minor_for_fre_at_or_above_40(self, english: EnglishAnalyzer) -> None:
        assert english.impact(65) == "minor"

    def test_returns_critical_for_italian_gulpease_below_40(self, italian: ItalianAnalyzer) -> None:
        assert italian.impact(30) == "critical"

    def test_returns_serious_for_italian_gulpease_below_50(self, italian: ItalianAnalyzer) -> None:
        assert italian.impact(45) == "serious"

    def test_returns_minor_for_italian_gulpease_at_or_above_60(self, italian: ItalianAnalyzer) -> None:
        assert italian.impact(70) == "minor"

    def test_uses_lix_impact_thresholds_for_french(self, french: FrenchAnalyzer) -> None:
        assert french.impact(75) == "critical"
        assert french.impact(65) == "serious"
        assert french.impact(55) == "moderate"
        assert french.impact(30) == "minor"

    def test_uses_zix_impact_thresholds_for_german(self, german: GermanAnalyzer) -> None:
        """blokkli's WSTF thresholds re-expressed on the ZIX scale (CEFR edges)."""
        assert german.impact(-5) == "critical"
        assert german.impact(-3) == "serious"
        assert german.impact(-1) == "moderate"
        assert german.impact(2) == "minor"


class TestAgentContext:
    """Agent context reference text tests."""

    def test_returns_cefr_reference_text_for_english(self, english: EnglishAnalyzer) -> None:
        context = english.agent_context()
        assert "CEFR Score Reference" in context
        assert "A1" in context
        assert "C2" in context

    def test_returns_gulpease_reference_text_for_italian(self, italian: ItalianAnalyzer) -> None:
        context = italian.agent_context()
        assert "Gulpease Score Reference" in context
        assert "Very easy" in context
        assert "Critical" in context

    def test_returns_lix_reference_text_for_french(self, french: FrenchAnalyzer) -> None:
        context = french.agent_context()
        assert "LIX Score Reference" in context
        assert "Very easy" in context

    def test_returns_zix_reference_text_for_german(self, german: GermanAnalyzer) -> None:
        """The German table is authored for ZIX (and in German, for the prompt)."""
        context = german.agent_context()
        assert "ZIX Score Reference" in context
        assert "A2" in context
        assert "C2" in context


class TestFleschToCefr:
    """The ``fleschToCefr`` correspondence table, boundary by boundary."""

    @pytest.mark.parametrize(
        ("score", "level"),
        [
            (100, "A1"),
            (90, "A1"),
            (89.9, "A2"),
            (80, "A2"),
            (79.9, "B1"),
            (70, "B1"),
            (69.9, "B2"),
            (60, "B2"),
            (59.9, "C1"),
            (50, "C1"),
            (49.9, "C2"),
            (0, "C2"),
            (-20, "C2"),
        ],
    )
    def test_maps_score_to_cefr(self, score: float, level: str) -> None:
        assert flesch_to_cefr(score) == level

    def test_english_analyzer_formats_scores_as_cefr(self, english: EnglishAnalyzer) -> None:
        assert english.cefr(75) == "B1"
        assert english.format_score(75) == "B1 (FRE 75.0)"


class TestScaleInfo:
    """Scale info tests."""

    def test_english_scale(self, english: EnglishAnalyzer) -> None:
        info = english.scale_info()
        assert info.thresholds == (50.0, 60.0)
        assert info.direction == "higher_easier"
        assert (info.scale_min, info.scale_max) == (45.0, 65.0)

    def test_french_scale(self, french: FrenchAnalyzer) -> None:
        info = french.scale_info()
        assert info.thresholds == (40.0, 59.0)
        assert info.direction == "higher_harder"

    def test_german_scale_is_the_fixed_zix_range(self, german: GermanAnalyzer) -> None:
        info = german.scale_info()
        assert (info.scale_min, info.scale_max) == (-10.0, 10.0)
        assert info.thresholds == (-2.0, 0.0)


class TestGermanTargetEquivalence:
    """The German gate: in target <=> ZIX >= 0 <=> CEFR in {A1, A2, B1}."""

    @pytest.mark.parametrize("score", [-10.0, -4.1, -4.0, -2.1, -2.0, -0.1, 0.0, 0.1, 2.0, 4.0, 10.0])
    def test_easy_band_matches_the_cefr_floor(self, german: GermanAnalyzer, score: float) -> None:
        is_easy = german.band(score) == "easy"
        assert is_easy is (score >= 0.0)
        assert is_easy is (german.cefr(score) in {"A1", "A2", "B1"})

    def test_build_score_reports_in_target_for_the_easy_band(self, german: GermanAnalyzer) -> None:
        assert build_score(german, 1.0).in_target is True
        assert build_score(german, -0.5).in_target is False


class TestNoCefrForFrenchAndItalian:
    def test_french_has_no_cefr(self, french: FrenchAnalyzer) -> None:
        assert french.cefr(30) is None

    def test_italian_has_no_cefr(self, italian: ItalianAnalyzer) -> None:
        assert italian.cefr(85) is None
