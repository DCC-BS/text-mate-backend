"""Unit tests for the simplification loop (docs/simplify_redesign.md section 14).

Everything here runs without an LLM and without ZIX: the rewriter and the scoring
service are stubs, and language detection is patched out. What is under test is the
orchestration -- which attempt is kept, what the retry is told, when a ``chunk_done``
may be emitted, and the section 14.1 per-unit gate -- because that is the part that has
no other check.

Most tests monkeypatch ``SIMPLIFY_MIN_UNIT_WORDS`` down to 1 so that :func:`merge_units`
does not fold short, hand-written test paragraphs into a single unit (the production
default of 100 would swallow every paragraph these tests use). The real default is
covered separately, in ``TestUnitMerging``.

The service is built with ``SimplifyService.__new__`` to bypass ``__init__`` (which
constructs an agent against a live LLM config), following
``tests/test_advisor_resolver.py``. There is no ``pytest-asyncio`` in this project, so
coroutines are driven with ``asyncio.run``.
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import fields as dataclass_fields
from typing import Any, cast, final

import pytest
from dcc_backend_common.llm_agent.postprocessing import replace_eszett
from pydantic_ai.models.test import TestModel

from text_mate_backend.agents.agent_types.quick_actions.plain_language_agent import PlainLanguageAgent
from text_mate_backend.models.simplify_models import (
    RewriteRequest,
    SimplifyChunkDoneEvent,
    SimplifyDoneEvent,
    SimplifyEvent,
    SimplifyProgressEvent,
    SimplifyStartEvent,
)
from text_mate_backend.readability.core.bands import build_score
from text_mate_backend.readability.types import ImpactLevel, LanguageCode, ReadabilityBand, ReferenceRow, ScaleInfo
from text_mate_backend.services import simplify_service as service_module
from text_mate_backend.services.simplify_service import SIMPLIFY_CHUNKING_THRESHOLD_CHARS, SimplifyService
from text_mate_backend.utils.configuration import Configuration

# =============================================================================
# STUBS
# =============================================================================


class StubAnalyzer:
    """A ZIX-shaped analyzer with the real band arithmetic and no model behind it.

    ``higher_easier``, easy at >= 0, exactly like German, so the numbers in these
    tests read the way the production ones do. Subclassed once, to get a
    ``higher_harder`` metric shaped like French LIX.
    """

    language: LanguageCode = "de"
    score_label: str = "ZIX"
    min_words: int = 3

    def score(self, text: str) -> float | None:
        raise AssertionError("the scoring service is stubbed; the analyzer must not be called directly")

    def band(self, score: float) -> ReadabilityBand:
        if score >= 0:
            return "easy"
        return "ok" if score >= -2 else "hard"

    def impact(self, score: float) -> ImpactLevel:
        if score >= 0:
            return "minor"
        return "moderate" if score >= -2 else "serious"

    def cefr(self, score: float) -> str | None:
        if score >= 2:
            return "A2"
        if score >= 0:
            return "B1"
        return "B2" if score >= -2 else "C1"

    def format_score(self, score: float) -> str:
        return f"ZIX {score:.1f}"

    def agent_context(self) -> str:
        return "## ZIX Score Reference"

    def reference_table(self) -> Sequence[ReferenceRow]:
        return ()

    def scale_info(self) -> ScaleInfo:
        return ScaleInfo(thresholds=(-2.0, 0.0), direction="higher_easier", scale_min=-10.0, scale_max=10.0)


@final
class StubScoring:
    """Stands in for ``TextAnalysisService``: a pure function from text to raw score."""

    def __init__(self, values: Callable[[str], float | None]) -> None:
        self.values = values
        self.scored: list[str] = []

    async def score(self, text: str, analyzer: Any) -> Any:
        self.scored.append(text)
        value = self.values(text)
        return build_score(analyzer, value) if value is not None else None

    async def score_many(self, texts: Sequence[str], analyzer: Any) -> list[Any]:
        return [await self.score(text, analyzer) for text in texts]


class StubRewriter:
    """Returns canned rewrites in order and records every request it was given.

    Subclassed by the failure tests, which need a rewriter that raises.
    """

    def __init__(self, outputs: Sequence[str]) -> None:
        self.outputs = list(outputs)
        self.requests: list[RewriteRequest] = []
        self.temperatures: list[float] = []

    async def rewrite(self, request: RewriteRequest, temperature: float = 0.0) -> str:
        self.requests.append(request)
        self.temperatures.append(temperature)
        index = min(len(self.requests) - 1, len(self.outputs) - 1)
        return self.outputs[index]


def make_service(
    rewriter: StubRewriter,
    scoring: StubScoring,
    *,
    max_attempts: int = service_module.SIMPLIFY_MAX_ATTEMPTS,
) -> SimplifyService:
    service = SimplifyService.__new__(SimplifyService)
    service.config = cast(Any, None)
    service.text_analysis_service = cast(Any, scoring)
    service.rewriter = cast(Any, rewriter)
    service.max_attempts = max_attempts
    return service


def patch_language(
    monkeypatch: Any,
    analyzer: StubAnalyzer | None,
    *,
    detected: str | None = "de",
    raw: tuple[str, float] | None = ("de", 0.99),
    min_unit_words: int = 1,
) -> None:
    """Replace fastText, the analyzer registry and the unit-merge target.

    ``min_unit_words`` defaults to 1 -- i.e. no merging -- so short, hand-written test
    paragraphs stay distinguishable units instead of collapsing into one under the
    production default of 100 (section 14.2). ``TestUnitMerging`` covers the real value.
    """
    monkeypatch.setattr(service_module, "detect_language", lambda text, min_chars=0: detected)
    monkeypatch.setattr(service_module, "detect_raw_language", lambda text, min_chars=0: raw)
    monkeypatch.setattr(service_module, "get_analyzer", lambda language: analyzer if language is not None else None)
    monkeypatch.setattr(service_module, "SIMPLIFY_MIN_UNIT_WORDS", min_unit_words)


def run_stream(service: SimplifyService, text: str, hint: str | None = None) -> list[SimplifyEvent]:
    async def collect() -> list[SimplifyEvent]:
        return [event async for event in service.simplify_stream(text, hint)]

    return asyncio.run(collect())


def only(events: Sequence[SimplifyEvent], kind: type) -> list[Any]:
    return [event for event in events if isinstance(event, kind)]


def done_of(events: Sequence[SimplifyEvent]) -> SimplifyDoneEvent:
    dones = only(events, SimplifyDoneEvent)
    assert len(dones) == 1, "exactly one done event must be emitted"
    assert events[-1] is dones[0], "done must be the last event on the stream"
    return cast(SimplifyDoneEvent, dones[0])


def scores(mapping: dict[str, float], default: float | None = None) -> Callable[[str], float | None]:
    return lambda text: mapping.get(text.strip(), default)


# =============================================================================
# WHOLE MODE
# =============================================================================

SOURCE = "Die Verfuegung ist bis zum 30. Juni 2025 anfechtbar und kostet 250 Franken."


class TestConvergence:
    def test_first_attempt_reaching_the_target_ends_the_loop(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        rewriter = StubRewriter(["Sie koennen die Verfuegung anfechten. Das kostet 250 Franken."])
        scoring = StubScoring(scores({SOURCE: -3.8}, default=1.5))
        service = make_service(rewriter, scoring)

        events = run_stream(service, SOURCE)
        done = done_of(events)

        assert len(rewriter.requests) == 1, "a passing pass-1 result must not trigger a retry"
        assert done.converged is True
        assert done.text == rewriter.outputs[0]
        assert done.score_before == -3.8
        assert done.score_after == 1.5
        assert done.band_after == "easy"
        assert done.scored is True

    def test_the_common_case_costs_exactly_one_llm_call(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        service = make_service(StubRewriter(["Kurz und klar."]), StubScoring(scores({SOURCE: -3.8}, default=1.5)))

        outcome = asyncio.run(service.simplify(SOURCE))

        assert outcome.llm_calls == 1
        assert outcome.attempts == 1

    def test_start_event_reports_the_source_measurement(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        service = make_service(StubRewriter(["Kurz und klar."]), StubScoring(scores({SOURCE: -3.8}, default=1.0)))

        start = cast(SimplifyStartEvent, run_stream(service, SOURCE)[0])

        assert start.event == "start"
        assert start.mode == "whole"
        assert start.scored is True
        assert start.language == "de"
        assert start.score_label == "ZIX"
        assert start.score_before == -3.8
        assert start.band_before == "hard"
        assert start.units == 1

    def test_pass_one_is_deterministic_and_the_retry_samples(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        rewriter = StubRewriter(["Immer noch schwer genug."])
        service = make_service(rewriter, StubScoring(scores({}, default=-3.0)))

        run_stream(service, SOURCE)

        assert len(rewriter.temperatures) == 2, "pass 1 plus exactly one retry"
        assert rewriter.temperatures[0] == service_module.SIMPLIFY_TEMPERATURE_FIRST == 0.0
        assert rewriter.temperatures[1] == service_module.SIMPLIFY_TEMPERATURE_RETRY
        assert service_module.SIMPLIFY_TEMPERATURE_RETRY > 0, "a deterministic retry reproduces the failure"


class TestRanking:
    """Ranking is by raw score, read in the analyzer's own direction."""

    def _attempt(self, number: int, value: float, analyzer: Any) -> Any:
        return service_module._Attempt(attempt=number, text=f"v{number}", score=build_score(analyzer, value))

    def test_higher_easier_picks_the_highest_score(self) -> None:
        analyzer = StubAnalyzer()
        attempts = [self._attempt(1, -0.5, analyzer), self._attempt(2, 2.0, analyzer), self._attempt(3, -3.0, analyzer)]

        best = service_module._best_attempt(attempts, "higher_easier")

        assert best is not None and best.attempt == 2

    def test_higher_harder_picks_the_lowest_score(self) -> None:
        """LIX is higher_harder: ranking on the raw value would pick the *worst* attempt."""

        @final
        class LixLike(StubAnalyzer):
            score_label: str = "LIX"

            def band(self, score: float) -> ReadabilityBand:
                return "easy" if score <= 40 else ("ok" if score <= 59 else "hard")

            def impact(self, score: float) -> ImpactLevel:
                return "minor" if score <= 40 else "serious"

            def cefr(self, score: float) -> str | None:
                return None

            def scale_info(self) -> ScaleInfo:
                return ScaleInfo(thresholds=(40.0, 59.0), direction="higher_harder", scale_min=20.0, scale_max=80.0)

        analyzer = LixLike()
        attempts = [
            self._attempt(1, 70.0, analyzer),
            self._attempt(2, 45.0, analyzer),
            self._attempt(3, 65.0, analyzer),
        ]

        best = service_module._best_attempt(attempts, "higher_harder")

        assert best is not None and best.attempt == 2

    def test_an_unscorable_attempt_ranks_below_every_scored_one(self) -> None:
        analyzer = StubAnalyzer()
        attempts = [
            service_module._Attempt(attempt=1, text="unscorable", score=None),
            self._attempt(2, -8.0, analyzer),
        ]

        best = service_module._best_attempt(attempts, "higher_easier")

        assert best is not None and best.attempt == 2

    def test_no_attempts_is_no_best(self) -> None:
        assert service_module._best_attempt([], "higher_easier") is None


class TestResolution:
    def test_the_pass_one_result_ships_even_when_the_retry_makes_it_worse(self, monkeypatch: Any) -> None:
        """A retry is not guaranteed to help; the best of the two ships, not the last."""
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        pass1, retry = "Bessere kurze Fassung hier.", "Schlechtere Fassung nun leider."
        rewriter = StubRewriter([pass1, retry])
        scoring = StubScoring(scores({SOURCE: -6.0, pass1: -0.5, retry: -3.0}))
        service = make_service(rewriter, scoring)

        done = done_of(run_stream(service, SOURCE))

        assert len(rewriter.requests) == 2, "pass 1 missed the target, so the one retry fired"
        assert done.text == pass1, "the retry was worse, so pass 1's own text ships"
        assert done.score_after == -0.5
        assert done.converged is False, "still outside the target band, so it is flagged for review"

    def test_a_hard_document_that_only_improves_still_ships_its_improvement(self, monkeypatch: Any) -> None:
        """C2 -> C1 but never B1: the real shape of a Basel-Stadt Ratschlag."""
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        source = "Der Regierungsrat beantragt dem Grossen Rat die Bewilligung des Rahmenkredits."
        pass1 = "Der Regierungsrat bittet um Geld fuer den Kredit."
        retry = "Der Regierungsrat bittet weiterhin um Geld fuer den Kredit."
        rewriter = StubRewriter([pass1, retry])
        scoring = StubScoring(scores({source: -5.7, pass1: -3.0, retry: -3.0}))
        service = make_service(rewriter, scoring)

        done = done_of(run_stream(service, source))

        assert done.cefr_after == "C1"
        assert done.score_after == -3.0
        assert done.converged is False
        assert done.unconverged_units == [0]

    def test_the_original_comes_back_only_when_nothing_usable_was_produced(self, monkeypatch: Any) -> None:
        @final
        class AlwaysFails(StubRewriter):
            async def rewrite(self, request: RewriteRequest, temperature: float = 0.0) -> str:
                self.requests.append(request)
                raise RuntimeError("vLLM went away")

        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        service = make_service(AlwaysFails([]), StubScoring(scores({SOURCE: -6.0})))

        done = done_of(run_stream(service, SOURCE))

        assert done.text == SOURCE, "a fallback, not a quality judgement"
        assert done.score_after == -6.0
        assert done.converged is False

    def test_a_failed_pass_one_does_not_trigger_a_unit_level_retry(self, monkeypatch: Any) -> None:
        """Retrying against an untouched original would not be 'one retry of a rewrite'."""

        @final
        class AlwaysFails(StubRewriter):
            async def rewrite(self, request: RewriteRequest, temperature: float = 0.0) -> str:
                self.requests.append(request)
                raise RuntimeError("vLLM went away")

        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        rewriter = AlwaysFails([])
        service = make_service(rewriter, StubScoring(scores({SOURCE: -6.0})))

        run_stream(service, SOURCE)

        assert len(rewriter.requests) == 1, "only the pass-1 call, no retry over the untouched original"

    def test_an_empty_generation_never_becomes_the_best_attempt(self, monkeypatch: Any) -> None:
        """An empty string scores as unscorable; shipping it would delete the document."""
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        service = make_service(StubRewriter(["   "]), StubScoring(scores({SOURCE: -6.0})))

        done = done_of(run_stream(service, SOURCE))

        assert done.text == SOURCE
        assert done.converged is False

    def test_attempts_are_capped_at_pass_one_plus_one_retry(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        rewriter = StubRewriter(["Immer noch zu schwer."])
        service = make_service(rewriter, StubScoring(scores({}, default=-5.0)))

        run_stream(service, SOURCE)

        assert service_module.SIMPLIFY_MAX_ATTEMPTS == 2, "pass 1 plus exactly one retry, by construction (§14.3)"
        assert len(rewriter.requests) == 2

    def test_a_failing_retry_resolves_from_what_survived(self, monkeypatch: Any) -> None:
        @final
        class FailsOnRetry(StubRewriter):
            async def rewrite(self, request: RewriteRequest, temperature: float = 0.0) -> str:
                self.requests.append(request)
                if len(self.requests) > 1:
                    raise RuntimeError("vLLM went away")
                return self.outputs[0]

        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        rewriter = FailsOnRetry(["Etwas besser hier."])
        scoring = StubScoring(scores({SOURCE: -6.0, "Etwas besser hier.": -1.0}))
        service = make_service(rewriter, scoring)

        done = done_of(run_stream(service, SOURCE))

        assert done.text == "Etwas besser hier.", "pass 1's result survives; the failed retry contributes nothing"
        assert done.score_after == -1.0
        assert done.converged is False


class TestUnconvergedUnits:
    def test_units_below_target_are_reported_after_the_retry(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        source = "Ein schwieriger Absatz hier drin.\n\nNoch ein schwieriger Absatz hier drin."
        pass1 = "Ein einfacher erster Absatz.\n\nEin harter Rest bleibt schwer hier."
        retry = "Ein harter Rest bleibt weiterhin schwer."
        scoring = StubScoring(
            scores(
                {
                    source: -5.0,
                    "Ein schwieriger Absatz hier drin.": -4.0,
                    "Noch ein schwieriger Absatz hier drin.": -4.0,
                    "Ein einfacher erster Absatz.": 3.0,
                    "Ein harter Rest bleibt schwer hier.": -3.0,
                    retry: -3.5,
                }
            )
        )
        rewriter = StubRewriter([pass1, retry])
        service = make_service(rewriter, scoring)

        done = done_of(run_stream(service, source))

        assert len(rewriter.requests) == 2, "unit 0 passed on pass 1; unit 1 got its one retry"
        assert done.converged is False
        assert done.unconverged_units == [1], "the retry did not fix it, so it is flagged for a human look"
        assert "Ein einfacher erster Absatz." in done.text


class TestUnconvergedRanges:
    """``unconverged_ranges`` (this task): character ranges into ``done.text`` -- the

    assembled output the client renders -- for each entry of ``unconverged_units``,
    in UTF-16 code units (the JS string indexing convention this project already
    established for ``ViolationRange``; see ``utils.text_offsets.to_utf16_offset``).
    """

    def test_ranges_land_on_the_shipped_unit_text(self, monkeypatch: Any) -> None:
        """WHOLE mode, two units: the offsets must survive unit 0 (in target, a
        different length than its source) shifting where unit 1 starts."""
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        source = "Ein schwieriger Absatz hier drin.\n\nNoch ein schwieriger Absatz hier drin."
        pass1 = "Ein einfacher erster Absatz.\n\nEin harter Rest bleibt schwer hier."
        retry = "Ein harter Rest bleibt weiterhin schwer."
        scoring = StubScoring(
            scores(
                {
                    source: -5.0,
                    "Ein schwieriger Absatz hier drin.": -4.0,
                    "Noch ein schwieriger Absatz hier drin.": -4.0,
                    "Ein einfacher erster Absatz.": 3.0,
                    "Ein harter Rest bleibt schwer hier.": -3.0,
                    retry: -3.5,
                }
            )
        )
        rewriter = StubRewriter([pass1, retry])
        service = make_service(rewriter, scoring)

        done = done_of(run_stream(service, source))

        assert done.unconverged_units == [1]
        assert len(done.unconverged_ranges) == 1
        shipped = "Ein harter Rest bleibt schwer hier."
        r = done.unconverged_ranges[0]
        assert done.text[r.start : r.end] == shipped, "the retry lost, so unit 1's own pass-1 text still ships"

    def test_zero_unconverged_units_yields_an_empty_list(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        rewriter = StubRewriter(["Sie koennen die Verfuegung anfechten. Das kostet 250 Franken."])
        scoring = StubScoring(scores({SOURCE: -3.8}, default=1.5))
        service = make_service(rewriter, scoring)

        done = done_of(run_stream(service, SOURCE))

        assert done.converged is True
        assert done.unconverged_units == []
        assert done.unconverged_ranges == []

    def test_chunked_mode_rewrite_with_a_different_length_still_maps_correctly(self, monkeypatch: Any) -> None:
        """CHUNKED mode: unit 1's shipped rewrite is far shorter than the source it
        replaced, and unit 0 (untouched) sits before it, so the range must be computed
        from the *assembled output*, not derived from source offsets."""
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        easy = "Dieser Absatz ist schon einfach genug fuer alle Leserinnen."
        hard = "Dieser Absatz bleibt leider dauerhaft zu schwer."
        source = long_document([easy, hard])
        padded_hard = source.split("\n\n")[1]

        shipped = "Etwas besser, aber nicht genug."
        rewriter = StubRewriter([shipped, "Noch schlechter geworden leider."])
        scoring = StubScoring(
            scores(
                {
                    easy: 3.0,
                    padded_hard: -6.0,
                    shipped: -1.0,
                    "Noch schlechter geworden leider.": -5.0,
                },
                default=-5.0,
            )
        )
        service = make_service(rewriter, scoring)

        done = done_of(run_stream(service, source))

        assert done.unconverged_units == [1]
        assert len(done.unconverged_ranges) == 1
        assert len(shipped) != len(padded_hard), "the fixture must actually exercise a length change"
        r = done.unconverged_ranges[0]
        assert done.text[r.start : r.end] == shipped

    def test_utf16_offsets_survive_a_non_bmp_character_earlier_in_the_text(self, monkeypatch: Any) -> None:
        """A regression back to Python code points would silently shift every range
        that follows a supplementary-plane character (emoji, here) by one per such
        character -- German umlauts are BMP, so this is the one case that catches it.
        """
        from text_mate_tools.run_advisor_eval import _utf16_to_codepoint_offset

        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        emoji_unit = "Dieser einfache Emoji-Absatz 🎉 bleibt unveraendert stehen hier."
        hard = "Dieser Absatz bleibt leider dauerhaft zu schwer."
        source = long_document([emoji_unit, hard])
        padded_hard = source.split("\n\n")[1]
        assert "🎉" in emoji_unit and ord("🎉") >= 0x10000, "must actually be a non-BMP character"

        shipped = "Etwas besser, aber nicht genug."
        rewriter = StubRewriter([shipped, "Noch schlechter geworden leider."])
        scoring = StubScoring(
            scores(
                {
                    emoji_unit: 3.0,
                    padded_hard: -6.0,
                    shipped: -1.0,
                    "Noch schlechter geworden leider.": -5.0,
                },
                default=-5.0,
            )
        )
        service = make_service(rewriter, scoring)

        done = done_of(run_stream(service, source))

        assert done.unconverged_units == [1]
        assert emoji_unit in done.text, "the emoji unit passes through unchanged, ahead of the unconverged unit"
        r = done.unconverged_ranges[0]

        # A code-point regression would leave this off by one and the slice below
        # would land one character short/long -- exactly the failure this test pins.
        codepoint_start = _utf16_to_codepoint_offset(done.text, r.start)
        codepoint_end = _utf16_to_codepoint_offset(done.text, r.end)
        assert done.text[codepoint_start:codepoint_end] == shipped


# =============================================================================
# MODE SELECTION
# =============================================================================


class TestModeSelection:
    def _mode_for(self, monkeypatch: Any, length: int) -> str:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        text = ("wort " * (length // 5 + 2))[:length]
        assert len(text) == length
        service = make_service(StubRewriter(["Kurz und einfach."]), StubScoring(scores({}, default=2.0)))
        start = cast(SimplifyStartEvent, run_stream(service, text)[0])
        return start.mode

    def test_whole_mode_at_the_threshold(self, monkeypatch: Any) -> None:
        assert SIMPLIFY_CHUNKING_THRESHOLD_CHARS == 10000
        assert self._mode_for(monkeypatch, SIMPLIFY_CHUNKING_THRESHOLD_CHARS) == "whole"

    def test_chunked_mode_one_character_above_the_threshold(self, monkeypatch: Any) -> None:
        assert self._mode_for(monkeypatch, SIMPLIFY_CHUNKING_THRESHOLD_CHARS + 1) == "chunked"

    def test_whole_mode_is_the_default_for_ordinary_text(self, monkeypatch: Any) -> None:
        assert self._mode_for(monkeypatch, 400) == "whole"


# =============================================================================
# CHUNKED MODE
# =============================================================================


def long_document(paragraphs: Sequence[str]) -> str:
    """Join paragraphs and pad the last one until the document is over the threshold."""
    filler = " Zusatz zur Laenge des Dokuments."
    text = "\n\n".join(paragraphs)
    while len(text) <= SIMPLIFY_CHUNKING_THRESHOLD_CHARS:
        text += filler
    return text


class TestChunkedMode:
    def test_only_failing_paragraphs_are_rewritten(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        easy = "Dieser Absatz ist schon einfach."
        hard = "Dieser Absatz ist deutlich zu schwer verstaendlich."
        source = long_document([easy, hard])
        padded_hard = source.split("\n\n")[1]

        rewriter = StubRewriter(["Dieser Absatz ist jetzt einfach."])
        scoring = StubScoring(scores({easy: 3.0, padded_hard: -4.0}, default=2.0))
        service = make_service(rewriter, scoring)

        events = run_stream(service, source)
        chunk_events = cast(list[SimplifyChunkDoneEvent], only(events, SimplifyChunkDoneEvent))

        assert len(rewriter.requests) == 1
        assert rewriter.requests[0].text == padded_hard, "the already-easy paragraph is left alone"
        assert [event.index for event in chunk_events] == [1]
        assert chunk_events[0].converged is True
        assert chunk_events[0].text == "Dieser Absatz ist jetzt einfach."
        assert easy in done_of(events).text, "untouched units are reassembled verbatim"

    def test_chunk_done_is_emitted_once_and_only_when_final(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        hard = "Dieser Absatz ist deutlich zu schwer verstaendlich."
        source = long_document([hard])

        first_try = "Immer noch etwas zu schwer formuliert."
        second_try = "Jetzt ist der Absatz einfach."
        rewriter = StubRewriter([first_try, second_try])
        scoring = StubScoring(scores({source: -4.0, first_try: -1.0, second_try: 2.5}, default=2.5))
        service = make_service(rewriter, scoring)

        events = run_stream(service, source)
        chunk_events = cast(list[SimplifyChunkDoneEvent], only(events, SimplifyChunkDoneEvent))

        assert len(rewriter.requests) == 2, "pass 1 plus the one retry"
        assert len(chunk_events) == 1, "the failing pass-1 attempt must not be announced as done"
        assert chunk_events[0].text == second_try
        assert chunk_events[0].attempts == 2
        assert chunk_events[0].converged is True

    def test_an_unconverged_paragraph_still_ships_its_best_attempt(self, monkeypatch: Any) -> None:
        """Same rule as WHOLE mode: the improvement ships, flagged for review."""
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        hard = "Dieser Absatz bleibt leider dauerhaft zu schwer."
        source = long_document([hard])

        rewriter = StubRewriter(["Etwas besser, aber nicht genug.", "Noch schlechter geworden leider."])
        scoring = StubScoring(
            scores(
                {
                    source: -6.0,
                    "Etwas besser, aber nicht genug.": -1.0,
                    "Noch schlechter geworden leider.": -5.0,
                },
                default=-5.0,
            )
        )
        service = make_service(rewriter, scoring)

        events = run_stream(service, source)
        chunk_events = cast(list[SimplifyChunkDoneEvent], only(events, SimplifyChunkDoneEvent))
        done = done_of(events)

        assert len(rewriter.requests) == 2, "pass 1 plus the one retry"
        assert len(chunk_events) == 1
        assert chunk_events[0].converged is False
        assert chunk_events[0].text == "Etwas besser, aber nicht genug.", "the best attempt, not the last"
        assert chunk_events[0].score_after == -1.0, "a real score, because a real rewrite shipped"
        assert done.text == "Etwas besser, aber nicht genug."
        assert done.unconverged_units == [0]
        assert done.converged is False

    def test_a_unit_whose_every_attempt_failed_keeps_its_original(self, monkeypatch: Any) -> None:
        @final
        class AlwaysFails(StubRewriter):
            async def rewrite(self, request: RewriteRequest, temperature: float = 0.0) -> str:
                self.requests.append(request)
                raise RuntimeError("vLLM went away")

        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        source = long_document(["Dieser Absatz bleibt leider dauerhaft zu schwer."])
        service = make_service(AlwaysFails([]), StubScoring(scores({}, default=-5.0)))

        events = run_stream(service, source)
        chunk_events = cast(list[SimplifyChunkDoneEvent], only(events, SimplifyChunkDoneEvent))

        assert chunk_events[0].text == source, "nothing usable was produced"
        assert chunk_events[0].score_after is None
        assert chunk_events[0].converged is False
        assert done_of(events).text == source

    def test_converged_is_per_unit_not_the_whole_document_band(self, monkeypatch: Any) -> None:
        """Section 14.1's reversal: every unit passing must report converged, even when
        the assembled document's own band would still read 'ok' rather than 'easy' --
        exactly the disagreement measured in docs/simplify_redesign.md §13.6 on
        ``initiative-erben-fuers-wohnen`` (83/83 paragraphs in target, document at -0.16)."""
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        stubborn = "Dieser Absatz laesst sich jetzt gut vereinfachen."
        fixable = "Dieser zweite Absatz laesst sich auch gut vereinfachen."
        source = long_document([stubborn, fixable])
        padded_fixable = source.split("\n\n")[1]

        attempt = "Jetzt einfach genug hier."
        assembled = f"{attempt}\n\n{padded_fixable}"
        rewriter = StubRewriter([attempt])

        def value_for(text: str) -> float | None:
            stripped = text.strip()
            if stripped == assembled:
                return -0.16  # the assembled document itself is still band "ok"
            if stripped in (attempt, padded_fixable):
                return 1.2  # but every individual unit is comfortably in target
            return -4.0  # the source and the stubborn unit before its rewrite

        service = make_service(rewriter, StubScoring(value_for))

        done = done_of(run_stream(service, source))

        assert done.converged is True, "both units reached target; the document number is reported, not gated on"
        assert done.score_after == -0.16, "the badge still shows the real, lower whole-document score"
        assert done.unconverged_units == []

    def test_neighbour_context_is_supplied_read_only(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        first = "Der erste Absatz ist bereits einfach."
        middle = "Der mittlere Absatz ist viel zu schwer verstaendlich."
        last = "Der letzte Absatz ist ebenfalls einfach."
        source = long_document([first, middle, last])
        padded_last = source.split("\n\n")[2]

        rewriter = StubRewriter(["Der mittlere Absatz ist jetzt einfach."])
        scoring = StubScoring(scores({first: 3.0, middle: -4.0, padded_last: 3.0}, default=3.0))
        service = make_service(rewriter, scoring)

        run_stream(service, source)

        context = rewriter.requests[0].neighbour_context
        assert context is not None
        assert context.previous_text == first
        assert context.following_text == padded_last
        assert context.document_summary is not None


# =============================================================================
# UNIT MERGING (section 14.2) -- the real, unpatched default
# =============================================================================


class TestUnitMerging:
    def test_short_paragraphs_are_gated_together_at_the_production_default(self, monkeypatch: Any) -> None:
        """Two short paragraphs must not each cost their own gate/retry decision.

        If the two pass-1 paragraphs below were scored individually they would each
        read "hard" (the stub default). Merged into one block -- section 14.2, still
        under 100 words but nothing left in the document to merge with -- they are
        scored together and read "easy". The retry never fires, and the two paragraph
        texts are never looked up on their own.
        """
        analyzer = StubAnalyzer()
        # min_unit_words left at the real default (100): patch_language's usual
        # override is skipped by passing it explicitly.
        patch_language(monkeypatch, analyzer, min_unit_words=service_module.DEFAULT_MIN_UNIT_WORDS)
        assert service_module.SIMPLIFY_MIN_UNIT_WORDS == 100

        source = "Text vor der Vereinfachung, lang genug zum Verarbeiten insgesamt hier."
        first = "Absatz eins ist kurz."
        second = "Absatz zwei ist auch kurz."
        rewritten = f"{first}\n\n{second}"
        rewriter = StubRewriter([rewritten])
        scoring = StubScoring(scores({source: -3.0, rewritten: 1.5}, default=-9.0))
        service = make_service(rewriter, scoring)

        events = run_stream(service, source)

        assert len(rewriter.requests) == 1, "the merged unit reached target on pass 1; no retry was needed"
        assert rewritten in scoring.scored, "the two short paragraphs were scored together, as one merged unit"
        assert first not in scoring.scored
        assert second not in scoring.scored
        assert done_of(events).converged is True


class TestUnitPopulationConsistency:
    """The "waaaay too many paragraphs" bug: ``start.units`` must report the same
    population ``progress.units_in_target`` is counted against -- merged, scorable
    units (section 14.2), never the raw blank-line blocks a document splits into
    before merging. On the real corpus a 258-block Ratschlag merges to 42 scorable
    units; this pins the same shape at a smaller, deterministic scale (200 raw
    blocks -> 20 merged units) and checks the two wire numbers agree."""

    def test_start_units_and_units_in_target_share_one_denominator(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        # The real default (100), not patch_language's usual override to 1: this bug
        # only shows up once paragraphs actually get merged forward.
        patch_language(monkeypatch, analyzer, min_unit_words=service_module.DEFAULT_MIN_UNIT_WORDS)
        assert service_module.SIMPLIFY_MIN_UNIT_WORDS == 100

        def paragraph(word: str) -> str:
            return " ".join([word] * 10) + "."

        # 190 ten-word "easy" paragraphs merge into 19 hundred-word blocks; 10 more
        # ten-word "hard" paragraphs merge into a 20th. 200 raw blocks, 20 merged
        # units -- a 10x gap, the same shape (if not the same size) as the real
        # corpus's 258 raw blocks / 42 merged units.
        easy_paragraphs = [paragraph("leicht") for _ in range(190)]
        hard_paragraphs = [paragraph("schwer") for _ in range(10)]
        source = "\n\n".join([*easy_paragraphs, *hard_paragraphs])
        assert len(source) > SIMPLIFY_CHUNKING_THRESHOLD_CHARS, "must exercise CHUNKED mode"

        raw_block_count = len(service_module.split_units(source, analyzer.min_words))
        assert raw_block_count == 200

        merged_easy_text = "\n\n".join([paragraph("leicht")] * 10)
        merged_hard_text = "\n\n".join([paragraph("schwer")] * 10)
        rewritten_hard = "Jetzt einfacher Absatz mit genuegend Woertern hier drin, um zu bestehen richtig."

        rewriter = StubRewriter([rewritten_hard])
        scoring = StubScoring(
            scores({merged_easy_text: 2.0, merged_hard_text: -4.0, rewritten_hard: 2.0}, default=-4.0)
        )
        service = make_service(rewriter, scoring)

        events = run_stream(service, source)
        start = cast(SimplifyStartEvent, events[0])
        progress_events = only(events, SimplifyProgressEvent)
        done = done_of(events)

        # The bug: `start` used to report `raw_block_count` (200) here.
        assert start.units == 20, "20 merged, scorable units -- not 200 raw blank-line blocks"
        assert start.units != raw_block_count, "the fixture must actually exercise merging"

        assert len(progress_events) == 1, "the one failing merged unit converges on pass 1, no retry needed"
        assert progress_events[0].units_in_target == 20, (
            "19 units were already in target; the 20th converged this attempt -- both counted "
            "over the same population `start.units` reports, not the 200 raw blocks"
        )
        assert progress_events[0].units_in_target == start.units, (
            "when every unit is in target, units_in_target must equal units -- the same "
            "population, read as one fraction ('X of Y units'), never two different ones"
        )
        assert done.converged is True
        assert done.unconverged_units == []


# =============================================================================
# UNSUPPORTED LANGUAGE
# =============================================================================


class TestUnsupportedLanguage:
    def test_single_shot_without_scoring_or_loop(self, monkeypatch: Any) -> None:
        patch_language(monkeypatch, None, detected=None, raw=("es", 0.98))
        rewriter = StubRewriter(["Texto simplificado."])
        scoring = StubScoring(scores({}, default=1.0))
        service = make_service(rewriter, scoring)

        events = run_stream(service, "Un texto administrativo en espanol que es bastante dificil de leer.")
        start = cast(SimplifyStartEvent, events[0])
        done = done_of(events)

        assert len(rewriter.requests) == 1, "no loop without a metric to close it"
        assert scoring.scored == [], "a number here would look authoritative and mean nothing"
        assert only(events, SimplifyProgressEvent) == []
        assert start.scored is False
        assert start.score_label is None
        assert start.language == "es"
        assert done.scored is False
        assert done.score_before is None and done.score_after is None
        assert done.text == "Texto simplificado."

    def test_the_generic_prompt_is_used_for_the_detected_language(self, monkeypatch: Any) -> None:
        patch_language(monkeypatch, None, detected=None, raw=("es", 0.98))
        rewriter = StubRewriter(["Texto simplificado."])
        service = make_service(rewriter, StubScoring(scores({})))

        run_stream(service, "Un texto administrativo en espanol.")

        assert rewriter.requests[0].language == "es"
        prompt = service_module.PlainLanguageAgent.build_prompt(cast(Any, None), rewriter.requests[0])
        assert "# HOW TO SIMPLIFY" in prompt, "no unreviewed German house style on a Spanish text"

    def test_a_failed_single_shot_returns_the_original(self, monkeypatch: Any) -> None:
        @final
        class BrokenRewriter(StubRewriter):
            async def rewrite(self, request: RewriteRequest, temperature: float = 0.0) -> str:
                self.requests.append(request)
                raise RuntimeError("vLLM went away")

        patch_language(monkeypatch, None, detected=None, raw=("es", 0.98))
        source = "Un texto administrativo en espanol."
        service = make_service(BrokenRewriter([]), StubScoring(scores({})))

        done = done_of(run_stream(service, source))

        assert done.text == source
        assert done.converged is False


# =============================================================================
# LANGUAGE RESOLUTION
# =============================================================================


class TestLanguageResolution:
    def test_detection_overrides_the_client_hint(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer, detected="de", raw=("de", 0.99))
        service = make_service(StubRewriter(["x"]), StubScoring(scores({})))

        assert service.detect("Ein deutscher Text.", "fr") == ("de", "de")

    def test_short_text_falls_back_to_the_hint(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer, detected=None, raw=None)
        service = make_service(StubRewriter(["x"]), StubScoring(scores({})))

        assert service.detect("Zu kurz.", "fr-CH") == ("de", "de"), "the stub registry answers de for every hint"

    def test_no_hint_and_no_detection_defaults_to_german(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(service_module, "detect_language", lambda text, min_chars=0: None)
        monkeypatch.setattr(service_module, "detect_raw_language", lambda text, min_chars=0: None)
        monkeypatch.setattr(service_module, "get_analyzer", lambda language: None)
        service = make_service(StubRewriter(["x"]), StubScoring(scores({})))

        assert service.detect("Zu kurz.", None) == (service_module.SIMPLIFY_FALLBACK_LANGUAGE, "de")

    def test_low_confidence_detection_is_treated_as_unknown(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer, detected=None, raw=("es", 0.2))
        service = make_service(StubRewriter(["x"]), StubScoring(scores({})))

        language, prompt_language = service.detect("Ein unklarer Text.", None)

        assert language == "de" and prompt_language == "de", "a coin-flip verdict must not disable scoring"


# =============================================================================
# EVAL CONFIGURATIONS
#
# The two entries of `build_simplifier`: the full loop and the single-shot baseline.
# They are the same class with different constructor arguments, so what these tests
# guard is that the argument actually reaches the loop.
# =============================================================================


class TestSimplifierProtocol:
    def test_the_service_satisfies_the_eval_harnesss_simplifier_protocol(self, monkeypatch: Any) -> None:
        """``run_simplify_eval.py`` drives the pipeline through this Protocol."""
        from text_mate_tools.simplify_eval.models import SimplifyOutput

        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        service = make_service(StubRewriter(["Kurz und klar."]), StubScoring(scores({SOURCE: -3.0}, default=2.0)))

        assert isinstance(SimplifyService.name, str)
        outcome = asyncio.run(service(SOURCE, "de"))

        # Field compatibility is the contract: the backend cannot import the harness's
        # model (the package dependency runs the other way), so this reconstructs it.
        outcome_fields = {field.name for field in dataclass_fields(outcome)}
        shared = set(SimplifyOutput.model_fields) & outcome_fields
        assert "text" in shared and "attempts" in shared and "converged" in shared
        harness_view = SimplifyOutput(**{name: getattr(outcome, name) for name in shared})
        assert harness_view.text == "Kurz und klar."
        assert harness_view.mode == "whole"
        assert harness_view.attempts == 1
        assert harness_view.llm_calls == 1
        assert harness_view.converged is True

    def test_llm_calls_are_counted_across_attempts(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        service = make_service(StubRewriter(["Immer noch zu schwer."]), StubScoring(scores({}, default=-5.0)))

        outcome = asyncio.run(service.simplify(SOURCE))

        assert outcome.attempts == 2, "pass 1 plus the one retry, by construction (§14.3)"
        assert outcome.llm_calls == 2, "one rewrite per attempt, and nothing else"
        assert outcome.converged is False


class TestSingleShotConfiguration:
    def test_max_attempts_one_stops_after_pass_one(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        rewriter = StubRewriter(["Immer noch viel zu schwer."])
        service = make_service(rewriter, StubScoring(scores({}, default=-5.0)), max_attempts=1)

        outcome = asyncio.run(service.simplify(SOURCE))

        assert len(rewriter.requests) == 1, "no retry in the baseline configuration"
        assert outcome.attempts == 1
        assert outcome.llm_calls == 1
        assert outcome.text == "Immer noch viel zu schwer.", "the single attempt still ships"
        assert outcome.converged is False, "the text never reached the target band"

    def test_the_baseline_still_keeps_a_rewrite_that_reached_target(self, monkeypatch: Any) -> None:
        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        service = make_service(
            StubRewriter(["Kurz und klar."]), StubScoring(scores({SOURCE: -6.0}, default=2.0)), max_attempts=1
        )

        outcome = asyncio.run(service.simplify(SOURCE))

        assert outcome.text == "Kurz und klar."
        assert outcome.converged is True

    def test_max_attempts_below_one_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            SimplifyService(fake_config(), cast(Any, None), max_attempts=0)


class TestEvalHarnessEntries:
    """``build_simplifier`` must produce both configurations, and only those."""

    def test_both_simplify_entries_are_wired_to_the_right_configuration(self, monkeypatch: Any) -> None:
        from text_mate_tools import run_simplify_eval

        built: list[dict[str, Any]] = []

        def fake_build(**kwargs: Any) -> Any:
            built.append(kwargs)
            return cast(Any, object())

        monkeypatch.setattr(run_simplify_eval, "build_simplify_service", fake_build)

        full = run_simplify_eval.build_simplifier("simplify")
        single = run_simplify_eval.build_simplifier("simplify_single_shot")

        assert full is not None and full.name == "simplify"
        assert single is not None and single.name == "simplify_single_shot"
        assert built == [
            {"max_attempts": service_module.SIMPLIFY_MAX_ATTEMPTS},
            {"max_attempts": 1},
        ]

    def test_the_adapter_translates_an_outcome_into_the_harness_model(self, monkeypatch: Any) -> None:
        from text_mate_tools.run_simplify_eval import SimplifyServiceSimplifier

        analyzer = StubAnalyzer()
        patch_language(monkeypatch, analyzer)
        service = make_service(StubRewriter(["Kurz und klar."]), StubScoring(scores({SOURCE: -3.0}, default=2.0)))
        simplifier = SimplifyServiceSimplifier("simplify", service)

        output = asyncio.run(simplifier(SOURCE, "de"))

        assert simplifier.name == "simplify"
        assert output.text == "Kurz und klar."
        assert output.mode == "whole"
        assert output.attempts == 1
        assert output.llm_calls == 1
        assert output.converged is True
        assert output.unconverged_units == []
        assert output.fidelity_failures == 0, "no runtime gate exists to report one"

    def test_the_retired_quick_action_baseline_explains_itself(self) -> None:
        from text_mate_tools.run_simplify_eval import build_simplifier

        with pytest.raises(ValueError, match="simplify_single_shot"):
            build_simplifier("quick_action")

    def test_an_unknown_name_is_still_an_error(self) -> None:
        from text_mate_tools.run_simplify_eval import build_simplifier

        with pytest.raises(ValueError, match="Unknown simplifier"):
            build_simplifier("nope")


# =============================================================================
# THE REWRITER
#
# Driven against pydantic-ai's TestModel: no network, but the real Agent, the real
# output schema and the real postprocessing pipeline.
# =============================================================================


def fake_config() -> Configuration:
    return Configuration(
        llm_model="test-model",
        llm_url="http://localhost:8001/v1",
        llm_api_key="test",
        llm_timeout=1,
        llm_max_retries=0,
        azure_client_id="",
        azure_tenant_id="",
        azure_frontend_client_id="",
        hmac_secret="test",
    )


class TestPlainLanguageAgent:
    def test_eszett_is_not_replaced_for_non_german_output(self) -> None:
        """Inherited from BaseAgent; it would mangle German names quoted in a French text."""
        agent = PlainLanguageAgent(fake_config())
        assert replace_eszett not in agent._postprocessors

        with agent._agent.override(model=TestModel(custom_output_text="Rue de la Weißenstein.")):
            output = asyncio.run(agent.rewrite(RewriteRequest(text="Un texte.", language="fr")))

        assert output == "Rue de la Weißenstein."

    def test_swiss_orthography_is_applied_to_german_output(self) -> None:
        agent = PlainLanguageAgent(fake_config())

        with agent._agent.override(model=TestModel(custom_output_text="Die Straße ist gesperrt.")):
            output = asyncio.run(agent.rewrite(RewriteRequest(text="Ein Text.", language="de")))

        assert output == "Die Strasse ist gesperrt."

    def test_the_dead_readability_tool_is_gone(self) -> None:
        """It computed ``text.split()`` counts that nothing ever asked for or read."""
        agent = PlainLanguageAgent(fake_config())
        assert not hasattr(agent, "check_readability_score")
        assert "check_readability_score" not in agent._agent._function_toolset.tools
