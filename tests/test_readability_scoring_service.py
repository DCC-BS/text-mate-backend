"""Unit tests for ``TextAnalysisService`` (no LLM; ZIX only where noted).

Most tests drive a stub analyzer so they exercise the service's own logic —
guards, memoization, the bounded thread pool — without paying for spaCy. The
``/text-analysis`` regression tests at the bottom use the real German analyzer,
because the whole point of them is that the existing endpoint keeps working.

The suite has no async plugin, so coroutines are driven with ``asyncio.run``.
``TextAnalysisService.__init__`` does no I/O (unlike ``AdvisorService``, which
is why ``tests/test_advisor_resolver.py`` bypasses it with ``__new__``), so the
service is constructed normally here.
"""

import asyncio
import threading
import time
from collections.abc import Coroutine, Sequence
from typing import Any, TypeVar, final

from text_mate_backend.models.text_analysis_models import TextAnalysisResult
from text_mate_backend.readability import detect_raw_language, is_supported
from text_mate_backend.readability.types import (
    BandConfig,
    ImpactLevel,
    LanguageCode,
    ReadabilityAnalyzer,
    ReadabilityBand,
    ReferenceRow,
    ScaleInfo,
)
from text_mate_backend.services.text_analysis_service import (
    MAX_SCORING_CHARS,
    UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE,
    TextAnalysisService,
)

T = TypeVar("T")

STUB_BANDS = BandConfig(direction="higher_easier", easy=60.0, ok=50.0, impact_thresholds=(40.0, 25.0, 10.0))

DE_TEXT = (
    "Die Katze sitzt auf der Matte. Der Hund rennt in den Park. "
    "Die Sonne scheint hell und warm. Die Kinder spielen im Garten."
)
EN_TEXT = (
    "The cat sat on the mat. The dog ran to the park. The sun was bright and warm. "
    "The kids played in the yard all afternoon."
)


def run(coro: Coroutine[Any, Any, T]) -> T:
    """Drive a coroutine to completion (the suite has no async plugin)."""
    return asyncio.run(coro)


@final
class StubAnalyzer:
    """A cheap, instrumented stand-in for a real analyzer."""

    def __init__(
        self,
        language: LanguageCode = "en",
        value: float | None = 70.0,
        raises: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.language: LanguageCode = language
        self.score_label = "STUB"
        self.min_words = 5
        self._value = value
        self._raises = raises
        self._delay = delay
        self.calls: list[str] = []
        self._lock = threading.Lock()
        self.concurrent = 0
        self.max_concurrent = 0

    def score(self, text: str) -> float | None:
        with self._lock:
            self.calls.append(text)
            self.concurrent += 1
            self.max_concurrent = max(self.max_concurrent, self.concurrent)
        try:
            if self._delay:
                time.sleep(self._delay)
            if self._raises is not None:
                raise self._raises
            return self._value
        finally:
            with self._lock:
                self.concurrent -= 1

    def band(self, score: float) -> ReadabilityBand:
        return "easy" if score >= STUB_BANDS.easy else "hard"

    def impact(self, score: float) -> ImpactLevel:
        return "minor" if score >= STUB_BANDS.easy else "critical"

    def cefr(self, score: float) -> str | None:
        return "B2"

    def format_score(self, score: float) -> str:
        return f"STUB {score:.1f}"

    def agent_context(self) -> str:
        return "## STUB Score Reference"

    def reference_table(self) -> Sequence[ReferenceRow]:
        return ()

    def scale_info(self) -> ScaleInfo:
        return ScaleInfo(thresholds=(50.0, 60.0), direction="higher_easier", scale_min=45.0, scale_max=65.0)


def make_service(max_workers: int = 2) -> TextAnalysisService:
    return TextAnalysisService(max_workers=max_workers)


def test_stub_satisfies_the_analyzer_protocol() -> None:
    assert isinstance(StubAnalyzer(), ReadabilityAnalyzer)


class TestScore:
    def test_returns_a_full_readability_score(self) -> None:
        analyzer = StubAnalyzer(value=70.0)
        result = run(make_service().score("a text with plenty of words in it", analyzer))

        assert result is not None
        assert result.language == "en"
        assert result.score == 70.0
        assert result.score_label == "STUB"
        assert result.band == "easy"
        assert result.in_target is True
        assert result.cefr == "B2"
        assert result.formatted == "STUB 70.0"

    def test_in_target_is_the_easy_band(self) -> None:
        analyzer = StubAnalyzer(value=10.0)
        result = run(make_service().score("a text with plenty of words in it", analyzer))

        assert result is not None
        assert result.band == "hard"
        assert result.in_target is False

    def test_empty_text_is_not_scored(self) -> None:
        analyzer = StubAnalyzer()
        assert run(make_service().score("   \n ", analyzer)) is None
        assert analyzer.calls == []

    def test_text_below_min_words_is_skipped_not_scored(self) -> None:
        analyzer = StubAnalyzer()
        assert run(make_service().score("Too short", analyzer)) is None
        assert analyzer.calls == []

    def test_over_long_text_is_refused_before_reaching_the_analyzer(self) -> None:
        """ZIX raises ValueError above 1M characters; that must not become a 500."""
        analyzer = StubAnalyzer()
        assert run(make_service().score("a " * MAX_SCORING_CHARS, analyzer)) is None
        assert analyzer.calls == []

    def test_analyzer_failure_becomes_none_instead_of_an_exception(self) -> None:
        analyzer = StubAnalyzer(raises=ValueError("Text too long (1000001 characters)."))
        assert run(make_service().score("a text with plenty of words in it", analyzer)) is None

    def test_unscorable_analyzer_result_becomes_none(self) -> None:
        analyzer = StubAnalyzer(value=None)
        assert run(make_service().score("a text with plenty of words in it", analyzer)) is None


class TestMemoization:
    def test_repeated_text_is_scored_once(self) -> None:
        service = make_service()
        analyzer = StubAnalyzer()
        text = "a text with plenty of words in it"

        async def scenario() -> tuple[object, object]:
            return await service.score(text, analyzer), await service.score(text, analyzer)

        first, second = run(scenario())
        assert first == second
        assert len(analyzer.calls) == 1

    def test_cache_key_includes_the_language(self) -> None:
        service = make_service()
        english = StubAnalyzer(language="en")
        french = StubAnalyzer(language="fr")
        text = "a text with plenty of words in it"

        async def scenario() -> None:
            await service.score(text, english)
            await service.score(text, french)

        run(scenario())
        assert len(english.calls) == 1
        assert len(french.calls) == 1

    def test_unscorable_results_are_cached_too(self) -> None:
        service = make_service()
        analyzer = StubAnalyzer(value=None)
        text = "a text with plenty of words in it"

        async def scenario() -> None:
            await service.score(text, analyzer)
            await service.score(text, analyzer)

        run(scenario())
        assert len(analyzer.calls) == 1


class TestScoreMany:
    def test_preserves_input_order_and_reports_unscorable_as_none(self) -> None:
        analyzer = StubAnalyzer(value=70.0)
        texts = [
            "the first paragraph with plenty of words",
            "short",
            "the second paragraph with plenty of words",
        ]
        results = run(make_service().score_many(texts, analyzer))

        assert len(results) == 3
        assert results[0] is not None
        assert results[1] is None
        assert results[2] is not None

    def test_duplicate_texts_are_scored_once(self) -> None:
        analyzer = StubAnalyzer()
        text = "a repeated paragraph with plenty of words"
        results = run(make_service().score_many([text, text, text], analyzer))

        assert len(analyzer.calls) == 1
        assert all(result == results[0] for result in results)

    def test_empty_input(self) -> None:
        assert run(make_service().score_many([], StubAnalyzer())) == []

    def test_uses_a_bounded_thread_pool(self) -> None:
        """40 paragraphs must not saturate the executor; ZIX is CPU-bound."""
        max_workers = 2
        analyzer = StubAnalyzer(delay=0.01)
        texts = [f"paragraph number {index} with plenty of words in it" for index in range(12)]

        results = run(make_service(max_workers=max_workers).score_many(texts, analyzer))

        assert len(results) == 12
        assert len(analyzer.calls) == 12
        assert analyzer.max_concurrent <= max_workers

    def test_scoring_is_actually_concurrent(self) -> None:
        analyzer = StubAnalyzer(delay=0.05)
        texts = [f"paragraph number {index} with plenty of words in it" for index in range(4)]

        start = time.monotonic()
        run(make_service(max_workers=4).score_many(texts, analyzer))
        elapsed = time.monotonic() - start

        assert analyzer.max_concurrent > 1
        assert elapsed < 0.05 * len(texts)

    def test_does_not_block_the_event_loop(self) -> None:
        analyzer = StubAnalyzer(delay=0.05)
        service = make_service(max_workers=2)
        ticks = 0

        async def tick() -> None:
            nonlocal ticks
            for _ in range(5):
                await asyncio.sleep(0.005)
                ticks += 1

        async def scenario() -> None:
            await asyncio.gather(
                service.score_many(["a paragraph with plenty of words in it"], analyzer),
                tick(),
            )

        run(scenario())
        assert ticks == 5


class TestAnalyzeEndpointCompatibility:
    """``POST /text-analysis`` regressions — the frontend CEFR badge reads these."""

    def test_german_text_still_returns_zix_score_and_cefr_level(self) -> None:
        result = run(make_service().analyze(DE_TEXT))

        assert isinstance(result, TextAnalysisResult)
        assert result.zix_score is not None
        assert -10.0 <= result.zix_score <= 10.0
        assert result.cefr_level in {"A1", "A2", "B1", "B2", "C1", "C2"}

    def test_german_text_also_carries_the_new_language_aware_fields(self) -> None:
        result = run(make_service().analyze(DE_TEXT))

        assert result.language == "de"
        assert result.score_label == "ZIX"
        assert result.score == result.zix_score
        assert result.band in {"easy", "ok", "hard"}

    def test_short_text_returns_nulls_rather_than_failing(self) -> None:
        result = run(make_service().analyze("Zu kurz."))

        assert result.zix_score is None
        assert result.cefr_level is None
        # Too short to detect and too short to score: nothing is claimed.
        assert result.language is None

    def test_over_long_text_does_not_raise(self) -> None:
        result = run(make_service().analyze("Das ist ein Satz. " * 60_000))

        assert result.zix_score is None
        assert result.score is None

    def test_english_text_is_scored_with_flesch_not_zix(self) -> None:
        result = run(make_service().analyze(EN_TEXT))

        assert result.language == "en"
        assert result.score_label == "CEFR"
        assert result.score is not None
        # zix_score keeps its name's meaning: a ZIX value, or nothing.
        assert result.zix_score is None
        assert result.cefr_level in {"A1", "A2", "B1", "B2", "C1", "C2"}

    def test_short_german_sentence_is_detected_and_scored(self) -> None:
        result = run(make_service().analyze("Anmeldung bis am 1. Mai einreichen bitte."))

        assert result.language == "de"
        assert result.score_label == "ZIX"
        assert result.zix_score is not None


class TestUnsupportedAndInconclusiveLanguages:
    """The two halves of "we could not score this", which must not be confused.

    A confident foreign verdict means "no score, and here is the language"; an
    unsure verdict means "assume German so the CEFR badge survives, and claim
    nothing about the language".
    """

    def test_confident_spanish_is_not_scored_and_is_reported_as_spanish(self) -> None:
        result = run(
            make_service().analyze(
                "La Administracion cantonal informa a los ciudadanos sobre el procedimiento "
                "de consulta previsto en la legislacion vigente para el proximo ano."
            )
        )

        assert result.language == "es"
        assert result.zix_score is None
        assert result.cefr_level is None
        assert result.score is None
        assert result.score_label is None
        assert result.band is None

    def test_confident_chinese_is_not_scored(self) -> None:
        result = run(make_service().analyze("这是一个中文句子，用于测试语言检测功能，希望它能正常工作。"))

        assert result.language == "zh"
        assert result.zix_score is None
        assert result.band is None

    def test_uncertain_verdict_keeps_the_german_badge_without_claiming_german(self) -> None:
        """A line of Swiss abbreviations: fastText says Swahili, at 0.13 confidence.

        Well below :data:`UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE`, so the endpoint
        scores it as German rather than blanking the badge — but reports no
        language, because none was established.
        """
        text = "AHV IV EL BVG UVG KVG ALV EO"
        detected = detect_raw_language(text)
        assert detected is not None
        assert detected[1] < UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE

        result = run(make_service().analyze(text))
        assert result.language is None
        assert result.score_label == "ZIX"
        assert result.zix_score is not None
        assert result.cefr_level is not None

    def test_low_confidence_foreign_verdict_does_not_blank_the_score(self) -> None:
        """ "Nr. 12 A B ..." reads as Dutch at 0.55 — unsupported, but not confidently."""
        text = "Nr. 12 A B C D E F G H I J K"
        detected = detect_raw_language(text)
        assert detected is not None
        assert not is_supported(detected[0])
        assert detected[1] < UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE

        result = run(make_service().analyze(text))
        assert result.language is None
        assert result.score_label == "ZIX"

    def test_threshold_is_the_only_thing_separating_the_two_branches(self) -> None:
        """Pinned at the boundary, so a threshold change cannot pass unnoticed."""
        service = make_service()

        def analyze_with_confidence(confidence: float) -> str | None:
            return service._confident_unsupported_language_from(("es", confidence))

        assert analyze_with_confidence(UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE) == "es"
        assert analyze_with_confidence(UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE - 0.01) is None
        # A supported language is never "unsupported", however confident.
        assert service._confident_unsupported_language_from(("de", 1.0)) is None
        assert service._confident_unsupported_language_from(None) is None
