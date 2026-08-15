"""Language detection tests.

Detection uses the bundled fastText ``lite`` model, so these tests run offline.
The important behaviours are the two guards: short texts and low-confidence
verdicts must come back as "unknown" (None) rather than as a wrong language,
and a language we cannot score must come back as None rather than as German.
"""

import pytest

from text_mate_backend.readability import SUPPORTED_LANGUAGES, get_analyzer, is_supported
from text_mate_backend.readability.detection import (
    MIN_DETECTION_CHARS,
    detect_language,
    detect_raw_language,
)

DE_TEXT = "Die Katze sitzt auf der Matte. Der Hund rennt in den Park. Die Sonne scheint hell und warm."
EN_TEXT = "The cat sat on the mat. The dog ran to the park. The sun was bright and warm today."
FR_TEXT = "Les réglementations gouvernementales complexes nécessitent des mécanismes de surveillance."
IT_TEXT = "Le complesse normative governative necessitano di straordinari meccanismi di supervisione."
ES_TEXT = "El gato se sentó en la alfombra y el perro corrió al parque bajo el sol brillante."


class TestDetectLanguage:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [(DE_TEXT, "de"), (EN_TEXT, "en"), (FR_TEXT, "fr"), (IT_TEXT, "it")],
    )
    def test_detects_the_supported_languages(self, text: str, expected: str) -> None:
        assert detect_language(text) == expected

    def test_unsupported_language_is_reported_as_unknown(self) -> None:
        """Spanish is detectable but not scorable, so detection reports None.

        None must never be read as "German": the caller skips scoring instead.
        """
        assert detect_raw_language(ES_TEXT) is not None
        assert detect_language(ES_TEXT) is None
        assert get_analyzer(detect_language(ES_TEXT)) is None

    def test_short_text_is_not_guessed(self) -> None:
        assert detect_language("Hallo") is None
        assert detect_language("") is None
        assert detect_language("   ") is None

    def test_min_chars_is_configurable(self) -> None:
        """Both guards are independent knobs; a short text needs both lowered.

        "Guten Tag." is detected as German, but only with 0.28 confidence —
        which is precisely why short texts are not trusted by default.
        """
        short_german = "Guten Tag."
        assert len(short_german) < MIN_DETECTION_CHARS
        assert detect_language(short_german) is None
        assert detect_language(short_german, min_chars=5) is None
        assert detect_language(short_german, min_chars=5, min_confidence=0.2) == "de"

    def test_confidence_floor_rejects_uncertain_verdicts(self) -> None:
        assert detect_language(DE_TEXT, min_confidence=1.01) is None

    def test_multiline_text_is_flattened_before_detection(self) -> None:
        multiline = "Die Katze sitzt auf der Matte.\n\nDer Hund rennt in den Park.\nDie Sonne scheint."
        assert detect_language(multiline) == "de"

    def test_result_is_always_a_supported_language(self) -> None:
        for text in (DE_TEXT, EN_TEXT, FR_TEXT, IT_TEXT, ES_TEXT):
            language = detect_language(text)
            assert language is None or language in SUPPORTED_LANGUAGES


class TestDetectRawLanguage:
    def test_returns_language_and_confidence(self) -> None:
        detected = detect_raw_language(DE_TEXT)
        assert detected is not None
        language, confidence = detected
        assert language == "de"
        assert 0.0 < confidence <= 1.0

    def test_reports_unsupported_languages_for_telemetry(self) -> None:
        detected = detect_raw_language(ES_TEXT)
        assert detected is not None
        assert detected[0] == "es"

    def test_returns_none_for_short_text(self) -> None:
        assert detect_raw_language("Hi") is None


class TestRegistry:
    def test_supported_languages_have_analyzers(self) -> None:
        for language in SUPPORTED_LANGUAGES:
            analyzer = get_analyzer(language)
            assert analyzer is not None
            assert analyzer.language == language
            assert analyzer.min_words > 0

    def test_unsupported_languages_have_no_analyzer(self) -> None:
        for language in ("es", "zh", "pt", "rm", "", "xx"):
            assert get_analyzer(language) is None
            assert is_supported(language) is False

    def test_language_codes_are_normalized(self) -> None:
        assert get_analyzer(" DE ") is not None
        assert get_analyzer(None) is None
