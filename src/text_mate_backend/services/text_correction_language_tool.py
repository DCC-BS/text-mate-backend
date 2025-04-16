import time
from typing import final

from returns.curry import partial
from returns.pipeline import flow
from returns.pointfree import map_
from returns.result import Failure, ResultE, Success

from text_mate_backend.models.language_tool_models import LanguageToolResponse
from text_mate_backend.models.text_corretion_models import (
    CorrectionBlock,
    CorrectionResult,
    TextCorrectionOptions,
)
from text_mate_backend.services.language_tool_service import LanguageToolService
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger("text_correction_service")


def _create_blocks(response: LanguageToolResponse) -> list[CorrectionBlock]:
    """Create correction blocks from the response."""
    blocks: list[CorrectionBlock] = []
    for match in response.matches:
        blocks.append(
            CorrectionBlock(
                original=match.context.text[match.context.offset : match.context.offset + match.context.length],
                corrected=list(map(lambda replacement: replacement.value, match.replacements)),
                explanation=match.message,
                offset=match.offset,
                length=match.length,
            )
        )
    logger.debug(f"Created {len(blocks)} correction blocks from matches")
    return blocks


@final
class TextCorrectionService:
    def __init__(self, config: Configuration, language_tool_Service: LanguageToolService) -> None:
        self.config = config
        self.language_tool = language_tool_Service
        logger.info("TextCorrectionService initialized")
        logger.debug(f"Using language tool API URL: {self.config.language_tool_api_url}")

    def correct_text(self, text: str, options: TextCorrectionOptions) -> ResultE[CorrectionResult]:
        """Corrects the input text based on given options.
        Returns Either[str, str] where:
        - Left(str) contains error message
        - Right(str) contains corrected text
        """
        text_snippet = text[:50] + ("..." if len(text) > 50 else "")
        logger.info("Processing text correction request", text_length=len(text), text_snippet=text_snippet)
        logger.debug("Correction options", language=options.language, writing_style=options.writing_style)

        start_time = time.time()
        blocks: ResultE[list[CorrectionBlock]] = flow(
            text,
            partial(self.language_tool.check_text, options.language),
            map_(_create_blocks),
        )
        processing_time = time.time() - start_time

        match blocks:
            case Success(value):
                logger.debug(
                    "Text correction completed successfully",
                    processing_time_ms=round(processing_time * 1000),
                    block_count=len(value),
                )
            case Failure(error):
                logger.error(
                    "Text correction failed", error=str(error), processing_time_ms=round(processing_time * 1000)
                )

        return blocks.map(lambda blocks: CorrectionResult(blocks=blocks, original=text))
