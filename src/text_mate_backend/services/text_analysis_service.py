import asyncio
from collections import OrderedDict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import final

from dcc_backend_common.logger import get_logger

from text_mate_backend.models.error_codes import TEXT_ANALYSIS_ERROR
from text_mate_backend.models.text_analysis_models import TextAnalysisResult
from text_mate_backend.readability import (
    MIN_CONFIDENCE,
    LanguageCode,
    ReadabilityAnalyzer,
    ReadabilityScore,
    build_score,
    detect_raw_language,
    get_analyzer,
    is_supported,
)
from text_mate_backend.readability.core.tokenize import segment_words

logger = get_logger("text_analysis_service")

#: ZIX is CPU-bound spaCy + sklearn. ``score_many`` over 40 paragraphs would
#: saturate asyncio's default executor (and starve every other ``to_thread``
#: caller in the process), so scoring gets its own small, bounded pool.
SCORING_MAX_WORKERS = 4

#: Memoization is keyed by ``(hash(text), language)`` and bounded; a request
#: rescoring the same paragraph across attempts is the case it exists for.
SCORE_CACHE_MAX_ENTRIES = 512

#: ZIX raises ``ValueError`` beyond spaCy's ``max_length``; refuse earlier and
#: return "not scorable" instead of a 500.
MAX_SCORING_CHARS = 1_000_000

#: ``POST /text-analysis`` predates language detection and is documented as a
#: German endpoint, so when detection is *inconclusive* it keeps behaving
#: exactly as before and scores with ZIX. The result then reports
#: ``language: null`` — the text is scored as German by assumption, which is not
#: the same as knowing it is German. This fallback is deliberately *local to
#: this endpoint*: ``score``/``score_many`` take an explicit analyzer, so the
#: simplify pipeline never scores non-German text with ZIX.
LEGACY_LANGUAGE: LanguageCode = "de"

#: A *confidently* detected language we cannot score gets no score at all — a
#: ZIX number for Spanish looks authoritative and means nothing
#: (docs/simplify_redesign.md section 3: "Do not fake a number").
#:
#: The threshold is higher than detection's own 0.5 floor because the two
#: mistakes cost different amounts: wrongly refusing to score German blanks the
#: CEFR badge the editor shows on every paragraph, while wrongly scoring a short
#: foreign fragment as German produces one meaningless number. So the endpoint
#: only gives up on scoring when detection is clearly sure.
#:
#: Measured on the fastText lite model: real German fragments score 0.66
#: ("Beilagen: Kopie Ausweis, Steuerbescheid") to 0.99, an ambiguous short
#: English sentence 0.55, while clearly foreign text sits at 0.90 (Spanish,
#: Dutch) to 0.999 (Chinese). 0.7 is the gap between those two populations.
UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE = 0.7

_CacheKey = tuple[int, str]


@final
class TextAnalysisService:
    """Scores text with a language-appropriate readability metric."""

    def __init__(self, max_workers: int = SCORING_MAX_WORKERS) -> None:
        logger.debug("Initializing TextAnalysisService", max_workers=max_workers)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="readability")
        self._cache: OrderedDict[_CacheKey, ReadabilityScore | None] = OrderedDict()
        self._cache_lock = Lock()

    async def analyze(self, text: str) -> TextAnalysisResult:
        """Compute the understandability score and CEFR level for a text.

        Three outcomes, and they are deliberately distinguishable:

        * **detected and scorable** — scored with that language's metric;
          ``language`` is the detected code;
        * **detected confidently but not scorable** (Spanish, Chinese, ...) —
          every score field is null and ``language`` is the language the text is
          actually in. No number is invented for it;
        * **detection inconclusive** (too short, too uncertain) — scored with
          ZIX as before, so the CEFR badge keeps working, with ``language: null``
          because nothing was established.

        Args:
            text: Text to analyze. Best results with paragraph-length input.

        Returns:
            TextAnalysisResult with ``zix_score``/``cefr_level`` (unchanged
            semantics for German) plus the language-aware ``language``,
            ``score``, ``score_label`` and ``band`` fields.
        """
        raw = detect_raw_language(text)
        if raw is not None:
            code, confidence = raw
            if confidence >= MIN_CONFIDENCE and is_supported(code):
                analyzer = get_analyzer(code)
                if analyzer is not None:
                    return await self._analyze_with(text, analyzer, code)

            unsupported = self._confident_unsupported_language_from(raw)
            if unsupported is not None:
                logger.debug("Text is in a language we do not score", language=unsupported)
                return TextAnalysisResult(zix_score=None, cefr_level=None, language=unsupported)

        # Inconclusive: assume German (this endpoint's historical behaviour) but
        # do not claim the text is German.
        legacy_analyzer = get_analyzer(LEGACY_LANGUAGE)
        if legacy_analyzer is None:
            logger.warning("No analyzer for language", language=LEGACY_LANGUAGE, error_code=TEXT_ANALYSIS_ERROR)
            return TextAnalysisResult(zix_score=None, cefr_level=None, language=None)
        return await self._analyze_with(text, legacy_analyzer, language=None)

    async def _analyze_with(self, text: str, analyzer: ReadabilityAnalyzer, language: str | None) -> TextAnalysisResult:
        """Score ``text`` with ``analyzer``, reporting ``language`` as detected.

        ``language`` is what detection established, not what the text was scored
        as: the two differ when detection was inconclusive.
        """
        result = await self.score(text, analyzer)
        if result is None:
            return TextAnalysisResult(
                zix_score=None,
                cefr_level=None,
                language=language,
                score_label=analyzer.score_label,
            )

        return TextAnalysisResult(
            # zix_score stays what its name says: a ZIX value or nothing.
            zix_score=result.score if result.language == "de" else None,
            cefr_level=result.cefr,
            language=language,
            score=result.score,
            score_label=result.score_label,
            band=result.band,
        )

    def _confident_unsupported_language(self, text: str) -> str | None:
        """The language of ``text`` when it is clearly one we cannot score."""
        return self._confident_unsupported_language_from(detect_raw_language(text))

    def _confident_unsupported_language_from(self, detected: tuple[str, float] | None) -> str | None:
        """Apply the confidence threshold to a raw detection result.

        Returns None when detection is merely inconclusive — a short or
        ambiguous text must not blank the score, only a confident foreign
        verdict may.
        """
        if detected is None:
            return None

        language, confidence = detected
        if confidence < UNSUPPORTED_LANGUAGE_MIN_CONFIDENCE:
            return None
        return None if is_supported(language) else language

    async def score(self, text: str, analyzer: ReadabilityAnalyzer) -> ReadabilityScore | None:
        """Score one text, or return None when it cannot be scored.

        Never raises: an unscorable text, an over-long text and a failing
        analyzer are all reported as None.
        """
        key = self._cache_key(text, analyzer)
        is_cached, cached = self._cache_get(key)
        if is_cached:
            return cached

        if not self._is_scorable(text, analyzer):
            self._cache_put(key, None)
            return None

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self._executor, self._score_sync, text, analyzer)
        self._cache_put(key, result)
        return result

    async def score_many(self, texts: Sequence[str], analyzer: ReadabilityAnalyzer) -> list[ReadabilityScore | None]:
        """Score many texts concurrently through the bounded pool.

        Duplicate texts are scored once. Results are returned in input order,
        with None for anything that could not be scored.
        """
        if not texts:
            return []

        unique: dict[_CacheKey, str] = {}
        keys = []
        for text in texts:
            key = self._cache_key(text, analyzer)
            keys.append(key)
            unique.setdefault(key, text)

        scores = await asyncio.gather(*(self.score(text, analyzer) for text in unique.values()))
        by_key = dict(zip(unique.keys(), scores, strict=True))
        return [by_key[key] for key in keys]

    def _is_scorable(self, text: str, analyzer: ReadabilityAnalyzer) -> bool:
        """Cheap guards, applied before a text is handed to the thread pool."""
        stripped = text.strip()
        if not stripped:
            return False

        if len(stripped) > MAX_SCORING_CHARS:
            logger.warning(
                "Text too long to score",
                error_code=TEXT_ANALYSIS_ERROR,
                length=len(stripped),
                limit=MAX_SCORING_CHARS,
                language=analyzer.language,
            )
            return False

        word_count = len(segment_words(stripped))
        if word_count < analyzer.min_words:
            logger.debug(
                "Text below min words, not scoring",
                words=word_count,
                min_words=analyzer.min_words,
                language=analyzer.language,
            )
            return False

        return True

    def _score_sync(self, text: str, analyzer: ReadabilityAnalyzer) -> ReadabilityScore | None:
        """Run the analyzer on a worker thread, converting failures into None."""
        try:
            value = analyzer.score(text)
        except Exception as exp:
            logger.error(
                "Readability scoring failed",
                error_code=TEXT_ANALYSIS_ERROR,
                language=analyzer.language,
                error=str(exp),
            )
            return None

        return build_score(analyzer, value) if value is not None else None

    def _cache_key(self, text: str, analyzer: ReadabilityAnalyzer) -> _CacheKey:
        return (hash(text), analyzer.language)

    def _cache_get(self, key: _CacheKey) -> tuple[bool, ReadabilityScore | None]:
        """Return ``(hit, value)``; a cached None is a result, not a miss."""
        with self._cache_lock:
            if key not in self._cache:
                return False, None
            self._cache.move_to_end(key)
            return True, self._cache[key]

    def _cache_put(self, key: _CacheKey, value: ReadabilityScore | None) -> None:
        with self._cache_lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > SCORE_CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)
