"""The simplification loop: measure -> rewrite -> re-measure -> retry.

Implements the pipeline of ``docs/simplify_redesign.md`` section 14, which supersedes the
original section 4.1/4.4 mode split after the first real-corpus measurement (section 13.6).
The orchestrator is deterministic Python and owns everything that decides; the LLM only
rewrites.

There is **one gate**, and it lives on the unit, not the document: a unit passes when its
own band is ``easy``. An LLM fidelity gate was built, measured and removed -- on the corpus
it rejected nothing that was actually wrong (every "lost" fact turned out to be the
spelled-out-number to digit conversion the Bundeskanzlei rules require), it disagreed with
itself across runs on the same input, and it doubled the call count of the common case.
Fact preservation is still *measured*, in the eval harness against hand-listed must-keep
facts, where a false positive costs a line in a report instead of a user's rewrite.
Information loss is therefore a prompt obligation (``REWRITE_COMPLETE``) and an eval metric,
not a runtime check.

Shape of a run (section 14.3)::

    detect language ─┬─ no analyzer ──> single rewrite, no scoring, no loop, scored=false
                     │
                     └─ analyzer ──> pass 1: whole document in one call
                                             (<= simplify_chunking_threshold_chars)
                                          else unit-wise: rewrite each merged unit that
                                             already fails, concurrently
                                     score every unit (merged to >= simplify_min_unit_words,
                                        section 14.2 -- a raw paragraph is too noisy to gate on)
                                     every unit in target -> done
                                     otherwise: exactly ONE retry per failing unit,
                                        fired concurrently, merged back into the pass-1 result

``simplify_max_attempts`` is 2 "by construction": pass 1 plus one retry round, not a general
N-attempt loop. The eval harness's single-shot baseline sets it to 1, which skips the retry
round entirely in both modes.

Two details are easy to get wrong and are therefore spelled out here:

* **The unit the gate operates on is a merged block, not a raw paragraph.** Measured ZIX
  deviation between a paragraph-length prefix and the full text is ~1.8 at the corpus
  median paragraph length (35 words) against bands that are 2 points wide -- gating on
  that would retry on measurement noise. Paragraphs are merged forward to >= 100 words
  (``simplify_min_unit_words``); headings and list items are barriers, never merged into
  or across (section 14.2). A merged unit that fails is retried as that merged block, not
  split back apart.
* **Resolution keeps the best attempt, not the last.** A retry is regularly worse than
  pass 1: the escalating instructions push towards shorter sentences, which can overshoot.
  "Best" is the best raw score, read in the analyzer's own direction. An attempt that
  improved the text but missed the target band is still shipped -- on hard Behörden
  documents (the corpus runs to ZIX -5.7) a C2 -> C1 rewrite is most of the value, and
  discarding it would hand the user an unchanged document after minutes of waiting, which
  the frontend then reports as "All good". Every change is reviewed hunk by hunk in
  ``DiffViewer`` before it lands, so shipping an improvement is not the same as imposing
  it. The **ORIGINAL** is returned only when no attempt produced usable output at all -- a
  fallback, not a quality judgement.
* **``converged`` is per-unit** (section 14.1, reversing the mode-independent whole-text
  definition of the original design): the whole-document band is no longer a gate, only
  a number that is still computed and reported (the one score the user sees, section
  14.4). ``converged`` on the ``done`` event is true exactly when no unit is left in
  ``unconverged_units`` -- it drives that shortfall hint, not the badge.
* **Every count on the wire describes the same population.** ``start.units``,
  ``progress.units_in_target`` and ``done.unconverged_units`` are all counted over
  ``rewritable_units(...)`` of the merged block list. Headings, list items and merged
  blocks still short of the analyzer's ``min_words`` are excluded from all three:
  they are permanent barriers or unscorable (``TextAnalysisService.score`` returns
  ``None`` for them).
"""

import asyncio
from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import final

import httpx
from dcc_backend_common.logger import get_logger

from text_mate_backend.agents.agent_types.quick_actions.plain_language_agent import PlainLanguageAgent
from text_mate_backend.models.simplify_models import (
    RewriteRequest,
    SimplifyChunkDoneEvent,
    SimplifyDoneEvent,
    SimplifyEvent,
    SimplifyMode,
    SimplifyOutcome,
    SimplifyProgressEvent,
    SimplifyStartEvent,
    UnconvergedRange,
)
from text_mate_backend.readability import (
    SUPPORTED_LANGUAGES,
    LanguageCode,
    ReadabilityAnalyzer,
    ReadabilityScore,
    detect_language,
    detect_raw_language,
    get_analyzer,
)
from text_mate_backend.readability.detection import MIN_CONFIDENCE, MIN_DETECTION_CHARS
from text_mate_backend.readability.types import ScoreDirection
from text_mate_backend.services.text_analysis_service import TextAnalysisService
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.simplify_chunker import (
    DEFAULT_MIN_UNIT_WORDS,
    DEFAULT_MIN_WORDS,
    TextUnit,
    merge_units,
    reassemble_with_spans,
    rewritable_units,
    split_units,
)
from text_mate_backend.utils.simplify_prompt import (
    NeighbourContext,
    PassingExample,
    PreviousAttempt,
    ScoreReference,
    is_german,
)
from text_mate_backend.utils.text_offsets import to_utf16_offset

logger = get_logger("simplify_service")


SIMPLIFY_CHUNKING_THRESHOLD_CHARS = 10000
"""Above this many characters, pass 1 rewrites unit by unit instead of in one call.

Raised from 8000 after section 13.6 measured that 12 of 16 real Basel-Stadt documents
exceed it -- CHUNKED is the normal path on real material, not the exception the original
8,000-char guess assumed. ``max_model_len`` is 198,944, so context is not the binding
constraint; T7.1 (docs section 7) owns re-deriving this against wall-clock and quality.
"""

SIMPLIFY_MAX_ATTEMPTS = 2
"""Pass 1, plus exactly one retry round for units still outside the target band.

Fixed at 2 "by construction" (section 14.3): this is no longer a general N-attempt loop.
The eval harness's single-shot baseline passes 1, which skips the retry round entirely.
"""

SIMPLIFY_MIN_UNIT_WORDS = DEFAULT_MIN_UNIT_WORDS
"""Merge paragraphs forward until a unit has this many words before gating (section 14.2).

100 gives ~2:1 merging on the real corpus while landing where the measured ZIX
prefix/full-text deviation is well under half a 2-point-wide band; at the raw-paragraph
median (35 words) the deviation is ~1.8 -- almost a full band, which would make the gate
retry on measurement noise rather than a real readability problem. Do not lower this
without new measurement (see the table in docs/simplify_redesign.md section 14.2).
"""

SIMPLIFY_TEMPERATURE_FIRST: float | None = 0.0
"""Attempt 1 is deterministic.

``None`` means "send no ``temperature`` at all and let the server decide". Production
never uses it; the eval harness does, to compare against a baseline that sets no
temperature either (``--server-default-temperature``, docs/simplify_redesign.md §15.7).
"""

SIMPLIFY_TEMPERATURE_RETRY: float | None = None
"""The retry samples uses models default temperature.

``None`` has the same meaning as on :data:`SIMPLIFY_TEMPERATURE_FIRST`.
"""

SIMPLIFY_MAX_PARALLEL_LLM_CALLS = 4
"""Concurrent unit rewrites, bounded so retries never fire unbounded (section 14.3).

Production serves with ``--max-num-seqs 256``; the dev box that produced the section 13.6
wall-clock figures runs ``--max-num-seqs 1``, so those numbers are the serialized worst
case, not the cost of the architecture.
"""

SIMPLIFY_REWRITE_TIMEOUT_SECONDS = 300
"""Per-rewrite timeout. Generous: a whole-document rewrite is a long generation."""

SIMPLIFY_EXEMPLAR_COUNT = 2
"""In-target units quoted back as style exemplars (blokkli's ``passingFields``)."""

SIMPLIFY_SUPPORTED_LANGUAGES: tuple[LanguageCode, ...] = SUPPORTED_LANGUAGES
"""Languages with an analyzer. Anything else is rewritten once and not scored."""

SIMPLIFY_LANGUAGE_DETECTION_MIN_CHARS = MIN_DETECTION_CHARS
"""Below this, fastText's verdict is not worth acting on (section 11)."""

SIMPLIFY_FALLBACK_LANGUAGE: LanguageCode = "de"
"""Used when detection is inconclusive and the client sent no usable hint."""

SIMPLIFY_SUMMARY_MAX_CHARS = 180
"""Length of the one-line document summary supplied as unit-retry context."""


@final
class ModelUnavailableError(RuntimeError):
    """The model could not be reached at all -- not "it answered badly".

    Raised instead of being counted, because the two need opposite handling. A bad
    answer is a per-unit problem: count it, keep the original for that unit, carry on
    with the rest. An unreachable model is a property of the *run*: every remaining
    unit will fail the same way, so continuing only burns wall-clock before arriving
    at the same unchanged text.

    That was measured, not assumed. One unreachable rewrite takes ~10s, because the
    OpenAI client's own retries stack on top of the tenacity transport in
    ``dcc_backend_common.llm_agent.base_agent`` (``llm_max_retries=2`` -> 3 transport
    attempts, times the SDK's own, with exponential backoff between). On a 23-unit
    document at 4 parallel calls that is ~1 minute for pass 1 and ~1 minute for the
    retry round -- two minutes of waiting to be told nothing changed. Aborting on the
    first one costs the ~10s of that single call's retries, which is the resilience
    against a transient blip that those retries exist for.
    """


def _is_unreachable(error: BaseException) -> bool:
    """True when ``error`` was caused by not reaching the model, at any depth.

    pydantic-ai wraps the transport failure twice (``ModelAPIError`` ->
    ``openai.APIConnectionError`` -> ``httpx.ConnectError``), so the cause chain is
    what carries the signal, not the type of the exception that surfaced. Both
    ``__cause__`` and ``__context__`` are followed, since a re-raise inside an
    ``except`` block links via the latter.

    ``httpx.TransportError`` is the whole family of "the request never got an answer":
    connect refused, DNS failure, connect/read/pool timeout, protocol error. A read
    timeout is included deliberately -- with ``llm_timeout`` at 300s it means five
    minutes of silence, which is as fatal to the run as a refused connection.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, httpx.TransportError):
            return True
        current = current.__cause__ or current.__context__
    return False


# =============================================================================
# INTERNAL STATE
# =============================================================================


@final
@dataclass(frozen=True, slots=True)
class _Attempt:
    """One recorded rewrite attempt of one unit (or of the whole text)."""

    attempt: int
    text: str
    score: ReadabilityScore | None

    @property
    def in_target(self) -> bool:
        return self.score is not None and self.score.in_target


@final
@dataclass(slots=True)
class SimplifyRunState:
    """Counters collected while a run streams, plus its final outcome.

    The stream is the primary interface; this is how a non-streaming caller (the
    eval harness, tests) gets the answer without re-deriving it from events.
    """

    llm_calls: int = 0
    #: Calls that returned nothing usable. Distinguishes "the model left this text
    #: alone" from "the model never answered", which are the same bytes on the wire.
    rewrite_failures: int = 0
    attempts: int = 0
    outcome: SimplifyOutcome | None = None


def _rank(attempt: _Attempt, direction: ScoreDirection) -> float:
    """Sort key for "best attempt": higher is better, whichever way the metric runs.

    LIX is ``higher_harder`` (a *lower* French score is easier), so ranking on the
    raw value without consulting the direction would systematically pick the worst
    French attempt.
    """
    if attempt.score is None:
        return float("-inf")
    return attempt.score.score if direction == "higher_easier" else -attempt.score.score


def _best_attempt(attempts: Sequence[_Attempt], direction: ScoreDirection) -> _Attempt | None:
    """The best-scoring attempt, or None when there are none.

    Bands are coarse, so attempts are ranked on the raw score even though the gate is
    the band (section 3, "Ranking"). Because the band is a monotone function of the
    score in the analyzer's direction, the best-ranked attempt is in target whenever
    *any* attempt is -- so the caller can decide "keep it or keep the original" from
    this one result.
    """
    if not attempts:
        return None
    return max(attempts, key=lambda attempt: _rank(attempt, direction))


def _normalize_language(code: str | None) -> str | None:
    """``"DE-CH"`` -> ``"de"``; empty and None stay None."""
    if not code:
        return None
    normalized = code.strip().lower().split("-")[0]
    return normalized or None


def _count_in_target(scores: Iterable[ReadabilityScore | None]) -> int:
    return sum(1 for score in scores if score is not None and score.in_target)


def _needs_rewrite(score: ReadabilityScore | None) -> bool:
    """Whether a scored unit is outside the target band -- the section 14.1 gate.

    An unscored unit (``None``) is never rewritten: the gate could not judge the
    result either, and an unverifiable rewrite is worse than no rewrite.
    """
    return score is not None and not score.in_target


def _unconverged_ranges(
    text: str, indices: Iterable[int], spans: Mapping[int, tuple[int, int]]
) -> list[UnconvergedRange]:
    """Unit spans in the assembled ``text``, converted to UTF-16 code units.

    ``spans`` (from :func:`reassemble_with_spans`) is in Python code points, the
    internal convention throughout this module; the conversion to UTF-16 code units
    happens here, once, at the API boundary -- via the shared
    :func:`~text_mate_backend.utils.text_offsets.to_utf16_offset` rather than
    reimplementing the BMP/surrogate-pair walk (see its docstring, and
    ``docs/simplify_redesign.md`` section 4.7).

    A unit index missing from ``spans`` (should not happen -- every index in
    ``indices`` comes from the same ``units`` list ``spans`` was built from) is
    skipped rather than raising: a missing highlight is a degraded UI, a crashed
    stream is a lost result.
    """
    ranges: list[UnconvergedRange] = []
    for index in indices:
        span = spans.get(index)
        if span is None:
            continue
        start, end = span
        ranges.append(
            UnconvergedRange(
                start=to_utf16_offset(text, start),
                end=to_utf16_offset(text, end),
            )
        )
    return ranges


@final
class SimplifyService:
    """Closed-loop simplification: the orchestrator of section 14.

    Also satisfies the eval harness's ``Simplifier`` Protocol
    (``text_mate_tools.simplify_eval.models``) via :attr:`name` and
    :meth:`__call__`, so ``run_simplify_eval.py`` can drive the real pipeline.
    The returned :class:`SimplifyOutcome` is field-compatible with the harness's
    ``SimplifyOutput``; the backend cannot import the harness's type because the
    package dependency runs the other way.
    """

    name = "simplify_service"

    def __init__(
        self,
        config: Configuration,
        text_analysis_service: TextAnalysisService,
        *,
        max_attempts: int = SIMPLIFY_MAX_ATTEMPTS,
        temperature_first: float | None = SIMPLIFY_TEMPERATURE_FIRST,
        temperature_retry: float | None = SIMPLIFY_TEMPERATURE_RETRY,
        name: str | None = None,
    ) -> None:
        """Build the pipeline. Production passes none of these keywords.

        ``max_attempts`` exists so the eval harness can run the *same* orchestration
        with the retry round switched off (``max_attempts=1`` is the single-shot
        baseline every later number is compared against); reconstructing that as a
        second code path would measure the fork rather than the loop. It is
        keyword-only and defaults to the section 14.5 constant, so the only way to
        get a degraded pipeline is to ask for one.

        ``temperature_first`` / ``temperature_retry`` exist for the same reason and are
        set to ``None`` together by ``--server-default-temperature``, which sends no
        ``temperature`` field at all. Only the eval uses that: the ``main`` baseline it
        is measured against never set a temperature either, so comparing the shipped
        schedule (0.0 / 0.4) against it confounds "the loop" with "the loop happens to
        be the only side running deterministically".
        """
        logger.debug("Initializing SimplifyService", max_attempts=max_attempts)
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self.config = config
        self.text_analysis_service = text_analysis_service
        self.rewriter = PlainLanguageAgent(config)
        self.max_attempts = max_attempts
        self.temperature_first = temperature_first
        self.temperature_retry = temperature_retry
        if name is not None:
            # Instance attribute shadowing the class default, so an eval report can
            # tell two configurations of the same service apart.
            self.name = name

    async def simplify_stream(self, text: str, language_hint: str | None = None) -> AsyncIterator[SimplifyEvent]:
        """Stream the run as section 4.7 events. ``done`` is always the last one."""
        state = SimplifyRunState()
        async for event in self._run(text, language_hint, state):
            yield event

    async def simplify(self, text: str, language_hint: str | None = None) -> SimplifyOutcome:
        """Run to completion and return the collected outcome."""
        state = SimplifyRunState()
        async for _ in self._run(text, language_hint, state):
            pass
        if state.outcome is None:  # pragma: no cover - _run always emits `done`
            return SimplifyOutcome(text=text, converged=False, scored=False)
        return state.outcome

    async def __call__(self, text: str, language: str) -> SimplifyOutcome:
        """Eval-harness entry point (``Simplifier`` Protocol)."""
        return await self.simplify(text, language)

    def detect(self, text: str, language_hint: str | None = None) -> tuple[LanguageCode | None, str | None]:
        """Resolve ``(analyzer language, language written to prompts and telemetry)``.

        Detection from the text wins over the client's hint, which is the UI locale
        and says nothing about the language of the text (section 1). Three outcomes:

        * a supported language -> both values are that language, the loop runs;
        * a confidently detected but unsupported language (``es``, ``pt``, ...) ->
          ``(None, "es")``: single rewrite, no scoring, no invented number;
        * inconclusive (too short, low confidence) -> fall back to the hint, then to
          German, and score after all (section 11).
        """
        supported = detect_language(text, min_chars=SIMPLIFY_LANGUAGE_DETECTION_MIN_CHARS)
        if supported is not None:
            return supported, supported

        detected = detect_raw_language(text, min_chars=SIMPLIFY_LANGUAGE_DETECTION_MIN_CHARS)
        if detected is not None:
            code, confidence = detected
            if confidence >= MIN_CONFIDENCE and code not in SIMPLIFY_SUPPORTED_LANGUAGES:
                # Confidently a language we have no calibrated metric for. Returning it
                # (rather than None) keeps the rewrite in the right language while the
                # loop and both gates stay switched off.
                return None, code

        hinted = get_analyzer(_normalize_language(language_hint))
        if hinted is not None:
            logger.debug("Language detection inconclusive, using client hint", hint=hinted.language)
            return hinted.language, hinted.language

        logger.debug(
            "Language detection inconclusive and no usable hint, defaulting",
            default=SIMPLIFY_FALLBACK_LANGUAGE,
        )
        return SIMPLIFY_FALLBACK_LANGUAGE, SIMPLIFY_FALLBACK_LANGUAGE

    async def _run(
        self,
        text: str,
        language_hint: str | None,
        state: SimplifyRunState,
    ) -> AsyncIterator[SimplifyEvent]:
        language, prompt_language = self.detect(text, language_hint)
        analyzer = get_analyzer(language)

        if analyzer is None:
            async for event in self._run_unscored(text, prompt_language, state):
                yield event
            return

        raw_units = split_units(text, analyzer.min_words)
        source_units = merge_units(raw_units, SIMPLIFY_MIN_UNIT_WORDS, analyzer.min_words)
        unit_count = len(rewritable_units(source_units))
        mode: SimplifyMode = "whole" if len(text) <= SIMPLIFY_CHUNKING_THRESHOLD_CHARS else "chunked"
        score_before = await self.text_analysis_service.score(text, analyzer)

        logger.info(
            "Simplify run starting",
            language=analyzer.language,
            mode=mode,
            chars=len(text),
            units=unit_count,
            score_before=score_before.score if score_before else None,
        )

        yield SimplifyStartEvent(
            language=analyzer.language,
            score_label=analyzer.score_label,
            scored=True,
            mode=mode,
            units=unit_count,
            score_before=score_before.score if score_before else None,
            band_before=score_before.band if score_before else None,
            cefr_before=score_before.cefr if score_before else None,
        )

        if mode == "whole":
            async for event in self._run_whole(text, analyzer, prompt_language, score_before, state):
                yield event
        else:
            async for event in self._run_chunked(text, source_units, analyzer, prompt_language, score_before, state):
                yield event

    async def _run_unscored(
        self,
        text: str,
        prompt_language: str | None,
        state: SimplifyRunState,
    ) -> AsyncIterator[SimplifyEvent]:
        """Unsupported language: one rewrite, no scoring, no loop (section 4.1 Stage 0).

        Faking a number here would be worse than reporting none: every band, every
        threshold and every retry decision downstream is calibrated per language, and
        an uncalibrated score would look authoritative while meaning nothing.
        """
        units = merge_units(split_units(text, DEFAULT_MIN_WORDS), SIMPLIFY_MIN_UNIT_WORDS, DEFAULT_MIN_WORDS)
        yield SimplifyStartEvent(
            language=prompt_language,
            score_label=None,
            scored=False,
            mode="whole",
            units=len(rewritable_units(units)),
        )

        yield SimplifyProgressEvent(attempt=1, stage="rewriting")

        state.attempts = 1
        rewritten = await self._rewrite(RewriteRequest(text=text, language=prompt_language, attempt=1), state)

        yield self._finish(
            state,
            text=rewritten if rewritten is not None else text,
            language=prompt_language,
            score_label=None,
            scored=False,
            mode="whole",
            score_before=None,
            score_after=None,
            converged=rewritten is not None,
            unconverged=(),
        )

    async def _run_whole(
        self,
        text: str,
        analyzer: ReadabilityAnalyzer,
        prompt_language: str | None,
        score_before: ReadabilityScore | None,
        state: SimplifyRunState,
    ) -> AsyncIterator[SimplifyEvent]:
        yield SimplifyProgressEvent(attempt=1, stage="rewriting", units_in_target=0)

        state.attempts = 1
        request = RewriteRequest(
            text=text,
            language=prompt_language,
            score_reference=self._score_reference(analyzer, score_before, prompt_language),
            attempt=1,
        )
        rewritten = await self._rewrite(request, state)
        pass1_text = rewritten if rewritten is not None else text

        pass1_score = await self.text_analysis_service.score(pass1_text, analyzer)
        units = merge_units(
            split_units(pass1_text, analyzer.min_words),
            SIMPLIFY_MIN_UNIT_WORDS,
            analyzer.min_words,
        )
        unit_scores = await self.text_analysis_service.score_many([unit.text for unit in units], analyzer)
        scores_by_index = {unit.index: score for unit, score in zip(units, unit_scores, strict=True)}
        rewritable = rewritable_units(units)
        unconverged = [unit.index for unit in rewritable if _needs_rewrite(scores_by_index[unit.index])]
        pass1_in_target = _count_in_target(scores_by_index[unit.index] for unit in rewritable)

        yield SimplifyProgressEvent(
            attempt=1,
            stage="readability",
            score=pass1_score.score if pass1_score else None,
            band=pass1_score.band if pass1_score else None,
            cefr=pass1_score.cefr if pass1_score else None,
            units_in_target=pass1_in_target,
        )

        replacements: dict[int, str] = {}
        # A retry only makes sense over a pass-1 result that actually came from the
        # model; a failed pass 1 already fell back to the original above.
        if unconverged and self.max_attempts > 1 and rewritten is not None:
            state.attempts = 2
            retried = len(unconverged)
            yield SimplifyProgressEvent(attempt=2, stage="rewriting", units_in_target=pass1_in_target)
            replacements, unconverged = await self._retry_units_once(
                units, unit_scores, analyzer, prompt_language, state, attempt=2
            )
            fixed = retried - len(unconverged)
            yield SimplifyProgressEvent(
                attempt=2,
                stage="readability",
                units_in_target=pass1_in_target + fixed,
            )

        final_text, unit_spans = reassemble_with_spans(units, replacements)
        score_after = await self.text_analysis_service.score(final_text, analyzer)

        yield self._finish(
            state,
            text=final_text,
            language=analyzer.language,
            score_label=analyzer.score_label,
            scored=True,
            mode="whole",
            score_before=score_before,
            score_after=score_after,
            converged=not unconverged,
            unconverged=unconverged,
            unit_spans=unit_spans,
        )

    # -------------------------------------------------------------------------
    # STAGE 2: CHUNKED mode (> simplify_chunking_threshold_chars only)
    # -------------------------------------------------------------------------

    async def _run_chunked(
        self,
        text: str,
        units: Sequence[TextUnit],
        analyzer: ReadabilityAnalyzer,
        prompt_language: str | None,
        score_before: ReadabilityScore | None,
        state: SimplifyRunState,
    ) -> AsyncIterator[SimplifyEvent]:
        direction = analyzer.scale_info().direction

        # `units` is already the merged block list (section 14.2), computed once in
        # `_run` -- the same list that produced `start.units`. Not re-derived here, so
        # the two counts can never drift apart (the bug this fixes: `start` used to
        # report raw, unmerged blocks while the gate below scored merged ones).
        unit_scores = await self.text_analysis_service.score_many([unit.text for unit in units], analyzer)

        by_index = {unit.index: unit for unit in units}
        scores_by_index = {unit.index: score for unit, score in zip(units, unit_scores, strict=True)}
        summary = self._document_summary(units)

        # Only rewritable units that are scored and outside the target are touched.
        # Headings, list items, units below min_words and units already in target
        # pass through verbatim: what cannot be verified must not be rewritten.
        #
        # `rewritable` is the same population `start.units` reports and `unconverged`
        # (below) is drawn from -- every count on this run's wire is this one list.
        rewritable = rewritable_units(units)
        already_in_target = _count_in_target(scores_by_index[unit.index] for unit in rewritable)
        pending = [unit.index for unit in rewritable if _needs_rewrite(scores_by_index[unit.index])]
        history: dict[int, list[_Attempt]] = {index: [] for index in pending}
        replacements: dict[int, str] = {}
        unconverged: list[int] = []

        semaphore = asyncio.Semaphore(SIMPLIFY_MAX_PARALLEL_LLM_CALLS)

        # The units already in target are the counter's starting value, and this is the
        # first event after `start`. Without it the client would show its initial state
        # -- attempt 1, "measuring readability", 0 in target -- for the entire first
        # round, which on a long document is minutes of the model actively rewriting.
        yield SimplifyProgressEvent(
            attempt=1,
            stage="rewriting",
            units_in_target=already_in_target,
        )

        for attempt in range(1, self.max_attempts + 1):
            if not pending:
                break
            state.attempts = attempt

            tasks = [
                asyncio.ensure_future(
                    self._process_unit(
                        by_index[index],
                        history[index],
                        attempt=attempt,
                        units=units,
                        scores_by_index=scores_by_index,
                        analyzer=analyzer,
                        prompt_language=prompt_language,
                        summary=summary,
                        semaphore=semaphore,
                        state=state,
                    )
                )
                for index in pending
            ]

            still_pending: list[int] = []
            try:
                for completed in asyncio.as_completed(tasks):
                    index, result = await completed
                    if result is not None:
                        history[index].append(result)
                        if result.in_target:
                            replacements[index] = result.text
                            yield self._chunk_done(
                                by_index[index],
                                scores_by_index[index],
                                result,
                                attempts=len(history[index]),
                                converged=True,
                            )
                        else:
                            still_pending.append(index)
                    else:
                        still_pending.append(index)

                    yield SimplifyProgressEvent(
                        attempt=attempt,
                        stage="rewriting",
                        units_in_target=already_in_target + len(replacements),
                    )
            finally:
                # Cancel running tasks if consumer disconnects
                for task in tasks:
                    if not task.done():
                        task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            pending = still_pending

            yield SimplifyProgressEvent(
                attempt=attempt,
                stage="readability",
                units_in_target=already_in_target + len(replacements),
            )

        for index in pending:
            best = _best_attempt(history[index], direction)
            unconverged.append(index)
            if best is not None:
                replacements[index] = best.text
            yield self._chunk_done(
                by_index[index],
                scores_by_index[index],
                best,
                attempts=len(history[index]),
                converged=False,
            )

        final_text, unit_spans = reassemble_with_spans(units, replacements)
        score_after = await self.text_analysis_service.score(final_text, analyzer)

        yield self._finish(
            state,
            text=final_text,
            language=analyzer.language,
            score_label=analyzer.score_label,
            scored=True,
            mode="chunked",
            score_before=score_before,
            score_after=score_after,
            converged=not unconverged,
            unconverged=sorted(unconverged),
            unit_spans=unit_spans,
        )

    async def _retry_units_once(
        self,
        units: Sequence[TextUnit],
        scores: Sequence[ReadabilityScore | None],
        analyzer: ReadabilityAnalyzer,
        prompt_language: str | None,
        state: SimplifyRunState,
        *,
        attempt: int,
    ) -> tuple[dict[int, str], list[int]]:
        """One concurrent retry round for units outside the target band (section 14.3).

        Used by WHOLE mode's post-pass-1 retry.
        """
        direction = analyzer.scale_info().direction
        by_index = {unit.index: unit for unit in units}
        scores_by_index = {unit.index: score for unit, score in zip(units, scores, strict=True)}
        summary = self._document_summary(units)

        pending = [unit.index for unit in rewritable_units(units) if _needs_rewrite(scores_by_index[unit.index])]
        replacements: dict[int, str] = {}
        unconverged: list[int] = []
        if not pending:
            return replacements, unconverged

        semaphore = asyncio.Semaphore(SIMPLIFY_MAX_PARALLEL_LLM_CALLS)
        baselines = {
            index: _Attempt(attempt=attempt - 1, text=by_index[index].text, score=scores_by_index[index])
            for index in pending
        }
        results = await asyncio.gather(
            *(
                self._process_unit(
                    by_index[index],
                    (baselines[index],),
                    attempt=attempt,
                    units=units,
                    scores_by_index=scores_by_index,
                    analyzer=analyzer,
                    prompt_language=prompt_language,
                    summary=summary,
                    semaphore=semaphore,
                    state=state,
                )
                for index in pending
            )
        )

        for index, retry_result in results:
            candidates = [candidate for candidate in (baselines[index], retry_result) if candidate is not None]
            best = _best_attempt(candidates, direction)
            if best is not None and best.text != baselines[index].text:
                replacements[index] = best.text
            if best is None or not best.in_target:
                unconverged.append(index)

        return replacements, sorted(unconverged)

    async def _process_unit(
        self,
        unit: TextUnit,
        history: Sequence[_Attempt],
        *,
        attempt: int,
        units: Sequence[TextUnit],
        scores_by_index: dict[int, ReadabilityScore | None],
        analyzer: ReadabilityAnalyzer,
        prompt_language: str | None,
        summary: str | None,
        semaphore: asyncio.Semaphore,
        state: SimplifyRunState,
    ) -> tuple[int, _Attempt | None]:
        """Rewrite and score one unit. Never raises.

        Returns ``(index, None)`` when the rewrite failed, so the caller can keep the
        unit pending without a partial record polluting the attempt history.
        """
        last = history[-1] if history else None
        previous = (
            PreviousAttempt(
                attempt=last.attempt,
                text=last.text,
                score=last.score.score if last.score else None,
                band=last.score.band if last.score else None,
            )
            if last is not None
            else None
        )

        request = RewriteRequest(
            text=unit.text,
            language=prompt_language,
            score_reference=self._score_reference(
                analyzer, last.score if last is not None else scores_by_index[unit.index], prompt_language
            ),
            previous_attempt=previous,
            passing_examples=self._examples(
                [other.text for other in units],
                [scores_by_index[other.index] for other in units],
                direction=analyzer.scale_info().direction,
                exclude=unit.index,
            ),
            neighbour_context=self._neighbour_context(unit, units, summary),
            exemplar_limit=SIMPLIFY_EXEMPLAR_COUNT,
            attempt=attempt,
        )

        async with semaphore:
            rewritten = await self._rewrite(request, state)
            if rewritten is None:
                return unit.index, None

            score = await self.text_analysis_service.score(rewritten, analyzer)

        return unit.index, _Attempt(attempt=attempt, text=rewritten, score=score)

    def _chunk_done(
        self,
        unit: TextUnit,
        before: ReadabilityScore | None,
        result: _Attempt | None,
        *,
        attempts: int,
        converged: bool,
    ) -> SimplifyChunkDoneEvent:
        """Build a ``chunk_done`` event. Only ever called once a unit cannot change."""
        return SimplifyChunkDoneEvent(
            index=unit.index,
            text=result.text if result is not None else unit.text,
            score_before=before.score if before else None,
            score_after=result.score.score if result is not None and result.score else None,
            cefr_before=before.cefr if before else None,
            cefr_after=result.score.cefr if result is not None and result.score else None,
            attempts=max(attempts, 1),
            converged=converged,
        )

    async def _rewrite(self, request: RewriteRequest, state: SimplifyRunState) -> str | None:
        """One rewrite, timeout-bounded. Returns None when it produced nothing usable."""
        state.llm_calls += 1
        temperature = self.temperature_first if request.attempt == 1 else self.temperature_retry
        try:
            rewritten = await asyncio.wait_for(
                self.rewriter.rewrite(request, temperature),
                timeout=SIMPLIFY_REWRITE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error("Rewrite timed out", attempt=request.attempt, timeout=SIMPLIFY_REWRITE_TIMEOUT_SECONDS)
            state.rewrite_failures += 1
            return None
        except Exception as exc:
            state.rewrite_failures += 1
            if _is_unreachable(exc):
                logger.error("Model unreachable, aborting run", attempt=request.attempt, error=str(exc))
                raise ModelUnavailableError(str(exc)) from exc
            logger.error("Rewrite failed", attempt=request.attempt, error=str(exc))
            return None

        if not rewritten or not rewritten.strip():
            logger.error("Rewrite returned empty output", attempt=request.attempt)
            state.rewrite_failures += 1
            return None
        return rewritten

    def _score_reference(
        self,
        analyzer: ReadabilityAnalyzer,
        score: ReadabilityScore | None,
        prompt_language: str | None,
    ) -> ScoreReference:
        """The analyzer's calibration, current score and reference table, as plain data."""
        scale = analyzer.scale_info()
        german = is_german(prompt_language)
        lower, upper = scale.thresholds
        easy_edge = upper if scale.direction == "higher_easier" else lower

        if german:
            span = f"{scale.scale_min:g} bis {scale.scale_max:g}"
            comparator = "oder höher" if scale.direction == "higher_easier" else "oder tiefer"
            target = f"Sprachniveau A2 oder B1 ({analyzer.score_label} {easy_edge:g} {comparator})"
        else:
            span = f"{scale.scale_min:g} to {scale.scale_max:g}"
            comparator = "or higher" if scale.direction == "higher_easier" else "or lower"
            target = f"{analyzer.score_label} {easy_edge:g} {comparator}"

        return ScoreReference(
            label=analyzer.score_label,
            score=score.score if score else None,
            band=score.band if score else None,
            cefr=score.cefr if score else None,
            scale=span,
            target=target,
            reference_table=analyzer.agent_context(),
        )

    def _examples(
        self,
        texts: Sequence[str],
        scores: Sequence[ReadabilityScore | None],
        direction: ScoreDirection,
        exclude: int | None = None,
    ) -> tuple[PassingExample, ...]:
        """Up to :data:`SIMPLIFY_EXEMPLAR_COUNT` in-target units, best first."""
        passing = [
            (index, text, score)
            for index, (text, score) in enumerate(zip(texts, scores, strict=True))
            if score is not None and score.in_target and index != exclude
        ]
        passing.sort(
            key=lambda item: item[2].score if direction == "higher_easier" else -item[2].score,
            reverse=True,
        )
        return tuple(
            PassingExample(index=index, text=text, score=score.score)
            for index, text, score in passing[:SIMPLIFY_EXEMPLAR_COUNT]
        )

    def _neighbour_context(
        self,
        unit: TextUnit,
        units: Sequence[TextUnit],
        summary: str | None,
    ) -> NeighbourContext:
        """Read-only surroundings of a unit, used whenever a unit is retried alone."""
        by_index = {other.index: other for other in units}
        previous = by_index.get(unit.index - 1)
        following = by_index.get(unit.index + 1)
        return NeighbourContext(
            previous_text=previous.text if previous else None,
            following_text=following.text if following else None,
            document_summary=summary,
        )

    def _document_summary(self, units: Sequence[TextUnit]) -> str | None:
        """A one-line "what this document is about", derived without an LLM call."""
        heading = next((unit for unit in units if unit.kind == "heading"), None)
        source = heading.text if heading is not None else (units[0].text if units else "")
        line = " ".join(source.split())
        if not line:
            return None
        return line if len(line) <= SIMPLIFY_SUMMARY_MAX_CHARS else line[:SIMPLIFY_SUMMARY_MAX_CHARS] + "..."

    def _finish(
        self,
        state: SimplifyRunState,
        *,
        text: str,
        language: str | None,
        score_label: str | None,
        scored: bool,
        mode: SimplifyMode,
        score_before: ReadabilityScore | None,
        score_after: ReadabilityScore | None,
        converged: bool,
        unconverged: Iterable[int],
        unit_spans: Mapping[int, tuple[int, int]] | None = None,
    ) -> SimplifyDoneEvent:
        """Build the ``done`` event and the run outcome from one set of values.

        Both are produced here so the stream and the non-streaming return value can
        never disagree about what happened. ``unit_spans`` is the by-index map
        :func:`~text_mate_backend.utils.simplify_chunker.reassemble_with_spans`
        returned alongside ``text``; omitted (``_run_unscored``, which never has an
        unconverged unit) it defaults to empty, which is also correct there.
        """
        indices = list(unconverged)
        ranges = _unconverged_ranges(text, indices, unit_spans or {})
        state.outcome = SimplifyOutcome(
            text=text,
            attempts=max(state.attempts, 1),
            llm_calls=state.llm_calls,
            rewrite_failures=state.rewrite_failures,
            converged=converged,
            mode=mode,
            unconverged_units=indices,
            unconverged_ranges=ranges,
            language=language,
            score_label=score_label,
            scored=scored,
            score_before=score_before.score if score_before else None,
            score_after=score_after.score if score_after else None,
            band_after=score_after.band if score_after else None,
            cefr_after=score_after.cefr if score_after else None,
        )
        logger.info(
            "Simplify run finished",
            language=language,
            mode=mode,
            attempts=state.attempts,
            llm_calls=state.llm_calls,
            rewrite_failures=state.rewrite_failures,
            converged=converged,
            unconverged_units=len(indices),
        )
        return SimplifyDoneEvent(
            text=text,
            language=language,
            score_label=score_label,
            scored=scored,
            score_before=score_before.score if score_before else None,
            score_after=score_after.score if score_after else None,
            band_after=score_after.band if score_after else None,
            cefr_after=score_after.cefr if score_after else None,
            converged=converged,
            unconverged_units=indices,
            unconverged_ranges=ranges,
            rewrite_failures=state.rewrite_failures,
        )
