"""Language detection (``fast-langdetect`` / fastText lid.176).

Detection runs once per request over the whole text and overrides the client's
UI-locale hint, which says nothing about the language the text is written in.

Two guards matter in practice:

* **Short texts.** fastText is unreliable below a few sentences -- it returns
  ``en`` with a confidence of 0.12 for an empty string -- so anything shorter
  than :data:`MIN_DETECTION_CHARS` or below :data:`MIN_CONFIDENCE` is reported
  as "unknown" (None) and the caller decides what to fall back to.
* **Model size.** The ``lite`` model (``lid.176.ftz``, ~1 MB) ships inside the
  ``fast_langdetect`` wheel; the ``auto``/``full`` default downloads a 125 MB
  model at first use. Only ``lite`` is used, so detection never needs the
  network.
"""

from typing import Final, Literal

from dcc_backend_common.logger import get_logger
from fast_langdetect import detect

from text_mate_backend.readability.registry import get_analyzer
from text_mate_backend.readability.types import LanguageCode

logger = get_logger("readability_detection")

#: Below this many characters, fastText's verdict is not worth acting on.
MIN_DETECTION_CHARS: Final[int] = 20

#: Below this confidence, the verdict is treated as "unknown".
MIN_CONFIDENCE: Final[float] = 0.5

#: Bundled model; never downloads anything.
_MODEL: Final[Literal["lite"]] = "lite"


def detect_raw_language(text: str, *, min_chars: int = MIN_DETECTION_CHARS) -> tuple[str, float] | None:
    """Detect the ISO 639-1 code and confidence of ``text``, without filtering.

    Returns None when the text is too short to judge or detection fails. Useful
    for telemetry: it distinguishes "Spanish" from "no idea", which
    :func:`detect_language` collapses into None.
    """
    stripped = text.strip()
    if len(stripped) < min_chars:
        return None

    # fastText predicts one line at a time; newlines are flattened first.
    flattened = " ".join(stripped.split())

    try:
        results = detect(flattened, model=_MODEL, k=1)
    except Exception as exc:
        # Detection must never break a request; an unknown language is a valid outcome.
        logger.warning("Language detection failed", error=str(exc))
        return None

    if not results:
        return None

    best = results[0]
    return str(best["lang"]).lower(), float(best["score"])


def detect_language(
    text: str,
    *,
    min_chars: int = MIN_DETECTION_CHARS,
    min_confidence: float = MIN_CONFIDENCE,
) -> LanguageCode | None:
    """Detect the language of ``text``, restricted to languages we can score.

    Returns None when the text is too short, the verdict is not confident
    enough, or the detected language has no analyzer. None means "do not score",
    never "score it as German".
    """
    stripped = text.strip()
    if len(stripped) < min_chars:
        return None

    detected = detect_raw_language(stripped, min_chars=min_chars)
    if detected is None:
        return None

    language, confidence = detected
    if confidence < min_confidence:
        logger.debug("Language detection below confidence floor", language=language, confidence=confidence)
        return None

    analyzer = get_analyzer(language)
    return analyzer.language if analyzer is not None else None
