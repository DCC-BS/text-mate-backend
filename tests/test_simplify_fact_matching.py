"""Tests for the eval harness's must-keep-facts comparison.

Guards against false-positive fact losses when numbers, dates, or currencies
are reformatted according to simplification guidelines.

See ``src/text_mate_tools/simplify_eval/normalize.py`` and docs/simplify_redesign.md §6.
"""

import pytest

from text_mate_tools.simplify_eval.normalize import fact_survives, missing_facts, normalize_for_fact_match


class TestPhantomLossesFromTheLiveRun:
    """The exact six facts of ``bs-merkblatt-betriebsbewilligung``, all of which survived."""

    @pytest.mark.parametrize(
        ("fact", "simplified"),
        [
            ("dreissig Tagen", "Sie muessen das innert 30 Tagen tun."),
            ("sechzig Tage", "Die Frist betraegt 60 Tage."),
            ("vierzehn Tagen", "Melden Sie sich innert 14 Tagen."),
            ("zwanzig Tagen", "Wir antworten innert 20 Tagen."),
            ("drei Monate", "Die Bewilligung gilt drei Monate."),
            ("40.50 Franken", "Die Gebuehr betraegt Fr. 40.50."),
        ],
    )
    def test_the_digit_conversion_the_rules_require_is_not_a_loss(self, fact: str, simplified: str) -> None:
        assert fact_survives(fact, simplified)


class TestCurrency:
    @pytest.mark.parametrize(
        "rendering",
        ["40.50 Franken", "Fr. 40.50", "CHF 40.50", "chf 40.50", "40.50 CHF", "40,50 Franken"],
    )
    def test_every_franc_rendering_is_the_same_amount(self, rendering: str) -> None:
        assert normalize_for_fact_match(rendering) == normalize_for_fact_match("CHF 40.50")

    def test_thousands_separators_do_not_matter(self) -> None:
        assert fact_survives("1'000 Franken", "Die Kaution betraegt CHF 1000.")

    def test_a_different_amount_is_still_a_loss(self) -> None:
        assert not fact_survives("40.50 Franken", "Die Gebuehr betraegt Fr. 45.50.")


class TestDates:
    @pytest.mark.parametrize("rendering", ["30. Juni 2025", "30.06.2025", "30.6.2025", "30. 6. 2025"])
    def test_every_date_rendering_is_the_same_day(self, rendering: str) -> None:
        assert normalize_for_fact_match(rendering) == normalize_for_fact_match("30.06.2025")

    def test_a_two_digit_year_is_expanded(self) -> None:
        assert fact_survives("30. Juni 2025", "Frist: 30.06.25")

    def test_a_different_day_is_still_a_loss(self) -> None:
        assert not fact_survives("30. Juni 2025", "Frist: 31.06.2025")


class TestNumberWords:
    @pytest.mark.parametrize(
        ("word", "digits"),
        [("dreissig", "30"), ("dreißig", "30"), ("zwölf", "12"), ("vierzehn", "14"), ("hundert", "100")],
    )
    def test_german_and_swiss_spellings_both_map_to_digits(self, word: str, digits: str) -> None:
        assert normalize_for_fact_match(word) == digits

    def test_articles_are_left_alone(self) -> None:
        """Turning 'ein Gesuch' into '1 gesuch' would mangle ordinary prose."""
        assert normalize_for_fact_match("ein Gesuch") == "ein gesuch"

    def test_compound_number_words_are_a_documented_limit(self) -> None:
        assert normalize_for_fact_match("einundzwanzig") == "einundzwanzig"


class TestRealLosses:
    """Normalization must not turn the measurement into a rubber stamp."""

    def test_a_dropped_deadline_is_reported(self) -> None:
        assert not fact_survives("30. Juni 2025", "Sie koennen die Verfuegung anfechten.")

    def test_a_dropped_amount_is_reported(self) -> None:
        assert not fact_survives("250 Franken", "Das Verfahren ist kostenlos.")

    def test_a_dropped_name_is_reported(self) -> None:
        assert not fact_survives("Bau- und Verkehrsdepartement", "Das Amt entscheidet.")

    def test_missing_facts_returns_the_original_wording(self) -> None:
        lost = missing_facts(["dreissig Tagen", "250 Franken"], "Innert 30 Tagen, kostenlos.")
        assert lost == ["250 Franken"], "the report quotes the case file, not the normalized form"


class TestNormalizationBasics:
    def test_case_and_whitespace_are_irrelevant(self) -> None:
        assert normalize_for_fact_match("  Die   FRIST\nbeträgt ") == "die frist betraegt"

    def test_trailing_punctuation_is_dropped_but_decimals_survive(self) -> None:
        assert normalize_for_fact_match("Es kostet 40.50.") == "es kostet 40.50"

    def test_an_empty_fact_is_vacuously_present(self) -> None:
        assert fact_survives("", "irgendein Text")
