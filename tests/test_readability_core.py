"""Tokenization, formula and band-mechanics vectors.

The tokenizers are a port of blokkli's ``getWords`` / ``getSentences`` /
``sentenceCount`` (MIT), which mirror ``@lunarisapp/language``. These tests pin
the behaviours the JavaScript originals rely on: punctuation stripped but
apostrophes kept, lowercasing, whitespace-run splitting, two-word sentence
fragments ignored, and a sentence count that never drops below 1.
"""

import pytest

from text_mate_backend.readability.core.bands import (
    build_agent_context,
    build_scale_info,
    classify_band,
    impact_for_score,
    in_target,
)
from text_mate_backend.readability.core.formulas import (
    FleschCoefficients,
    flesch_reading_ease,
    gulpease_index,
    lix,
    round_score,
    safe_score,
)
from text_mate_backend.readability.core.tokenize import (
    avg_sentence_length,
    avg_syllables_per_word,
    char_count,
    get_sentences,
    get_words,
    long_word_count,
    polysyllable_count,
    segment_words,
    sentence_count,
    word_count,
)
from text_mate_backend.readability.types import BandConfig, ReferenceRow


class TestGetWords:
    def test_strips_punctuation_and_lowercases(self) -> None:
        assert get_words("The quick, brown fox!") == ["the", "quick", "brown", "fox"]

    def test_keeps_apostrophes_for_contractions(self) -> None:
        assert get_words("don't stop") == ["don't", "stop"]

    def test_keeps_numbers_and_accented_letters(self) -> None:
        assert get_words("Am 1. Mai kostet es 20 Fr. für Bürger") == [
            "am",
            "1",
            "mai",
            "kostet",
            "es",
            "20",
            "fr",
            "für",
            "bürger",
        ]

    def test_drops_underscores_like_the_javascript_original(self) -> None:
        """JS keeps only ``\\p{L}\\p{N}\\s'``; Python's ``\\w`` also has ``_``."""
        assert get_words("snake_case word") == ["snakecase", "word"]

    def test_splits_on_whitespace_runs(self) -> None:
        assert get_words("a  \n\t b") == ["a", "b"]

    def test_empty_text_has_no_words(self) -> None:
        assert get_words("") == []
        assert get_words("!!! ???") == []


class TestSentences:
    def test_splits_on_terminal_punctuation(self) -> None:
        assert get_sentences("One. Two! Three?") == ["One.", " Two!", " Three?"]

    def test_ignores_fragments_of_two_words_or_fewer(self) -> None:
        assert sentence_count("The cat sat on the mat. The dog ran away. Ok.") == 2

    def test_never_returns_less_than_one(self) -> None:
        assert sentence_count("Hi.") == 1
        assert sentence_count("") == 1

    def test_counts_newlines_as_sentence_boundaries(self) -> None:
        assert sentence_count("Der erste lange Satz hier\nDer zweite lange Satz hier\n") == 2


class TestCounts:
    def test_word_count(self) -> None:
        assert word_count("The cat sat on the mat.") == 6

    def test_long_word_count_uses_a_threshold_of_six(self) -> None:
        # "komplexen" (9) and "Vorschriften" (12) are long; "sind" and "lang" are not.
        assert long_word_count("Die komplexen Vorschriften sind lang.") == 2
        assert long_word_count("sieben7", threshold=6) == 1
        assert long_word_count("sechs6", threshold=6) == 0

    def test_char_count_ignores_whitespace_but_keeps_punctuation(self) -> None:
        assert char_count("ab cd\nef.") == 7

    def test_avg_sentence_length(self) -> None:
        assert avg_sentence_length("The cat sat on the mat. The dog ran to the park.") == 6.0

    def test_avg_syllables_per_word(self) -> None:
        assert avg_syllables_per_word("aa bb cc", lambda word: len(word)) == 2.0
        assert avg_syllables_per_word("", lambda word: 1) == 0.0

    def test_polysyllable_count(self) -> None:
        assert polysyllable_count("a bb cccc ddddd", lambda word: len(word)) == 2

    def test_segment_words_counts_word_like_segments(self) -> None:
        assert segment_words("Too short.") == ["Too", "short"]
        assert segment_words("") == []
        assert segment_words("Es kostet 20 Franken.") == ["Es", "kostet", "20", "Franken"]


class TestFormulas:
    def test_flesch_reading_ease(self) -> None:
        coefficients = FleschCoefficients(base=206.835, sentences=1.015, syllables_per_word=84.6)
        assert flesch_reading_ease(10, 1.5, coefficients) == pytest.approx(69.785)

    def test_gulpease_index(self) -> None:
        assert gulpease_index(2, 100, 20) == pytest.approx(69.0)

    def test_lix(self) -> None:
        assert lix(20, 5, 10.0) == pytest.approx(35.0)

    def test_lix_returns_zero_without_words(self) -> None:
        assert lix(0, 0, 0.0) == 0.0

    def test_safe_score_swallows_division_by_zero(self) -> None:
        assert safe_score(lambda: 1.0 / 0.0) is None
        assert safe_score(lambda: float("inf")) is None
        assert safe_score(lambda: float("nan")) is None
        assert safe_score(lambda: 1.5) == 1.5

    def test_round_score_matches_javascript_math_round(self) -> None:
        assert round_score(2.25) == 2.3
        assert round_score(-2.25) == -2.2  # JS rounds halves towards +Infinity
        assert round_score(2.349) == 2.3
        assert round_score(-3.75) == -3.7


class TestBands:
    higher_easier = BandConfig(direction="higher_easier", easy=60.0, ok=50.0, impact_thresholds=(40.0, 25.0, 10.0))
    higher_harder = BandConfig(direction="higher_harder", easy=40.0, ok=59.0, impact_thresholds=(50.0, 60.0, 70.0))

    def test_higher_easier_band_edges_are_inclusive(self) -> None:
        assert classify_band(60, self.higher_easier) == "easy"
        assert classify_band(59.9, self.higher_easier) == "ok"
        assert classify_band(50, self.higher_easier) == "ok"
        assert classify_band(49.9, self.higher_easier) == "hard"

    def test_higher_harder_band_edges_are_inclusive(self) -> None:
        assert classify_band(40, self.higher_harder) == "easy"
        assert classify_band(40.1, self.higher_harder) == "ok"
        assert classify_band(59, self.higher_harder) == "ok"
        assert classify_band(59.1, self.higher_harder) == "hard"

    def test_impact_for_higher_easier(self) -> None:
        assert impact_for_score(9.9, self.higher_easier) == "critical"
        assert impact_for_score(10, self.higher_easier) == "serious"
        assert impact_for_score(24.9, self.higher_easier) == "serious"
        assert impact_for_score(25, self.higher_easier) == "moderate"
        assert impact_for_score(40, self.higher_easier) == "minor"

    def test_impact_for_higher_harder(self) -> None:
        assert impact_for_score(70, self.higher_harder) == "critical"
        assert impact_for_score(60, self.higher_harder) == "serious"
        assert impact_for_score(50, self.higher_harder) == "moderate"
        assert impact_for_score(49.9, self.higher_harder) == "minor"

    def test_in_target_is_the_easy_band(self) -> None:
        assert in_target(60, self.higher_easier) is True
        assert in_target(59, self.higher_easier) is False
        assert in_target(40, self.higher_harder) is True
        assert in_target(41, self.higher_harder) is False

    def test_scale_info_pads_by_half_the_threshold_distance(self) -> None:
        info = build_scale_info(self.higher_easier)
        assert info.thresholds == (50.0, 60.0)
        assert (info.scale_min, info.scale_max) == (45.0, 65.0)

    def test_scale_info_never_goes_below_zero_generically(self) -> None:
        config = BandConfig(direction="higher_easier", easy=8.0, ok=2.0, impact_thresholds=(2.0, 1.0, 0.0))
        assert build_scale_info(config).scale_min == 0.0

    def test_agent_context_renders_a_markdown_table(self) -> None:
        context = build_agent_context("LIX", [ReferenceRow("Below 25", "Very easy")])
        assert context == "## LIX Score Reference\n\n- Below 25: Very easy"
