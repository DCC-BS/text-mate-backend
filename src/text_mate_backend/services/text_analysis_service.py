import asyncio
from typing import final

from zix.understandability import get_cefr, get_zix

from text_mate_backend.models.text_analysis_models import TextAnalysisResult


@final
class TextAnalysisService:
    async def analyze(self, text: str) -> TextAnalysisResult:
        """Compute ZIX understandability score and CEFR level for German text.

        Args:
            text: German text to analyze. Best results with paragraph-length input.

        Returns:
            TextAnalysisResult with zix_score and cefr_level; both None if text is too short.
        """
        zix_score = await asyncio.to_thread(get_zix, text)
        cefr_level = get_cefr(zix_score) if zix_score is not None else None
        return TextAnalysisResult(zix_score=zix_score, cefr_level=cefr_level)
