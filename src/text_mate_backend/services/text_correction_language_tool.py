from typing import final

from returns.pipeline import flow
from returns.pointfree import map_
from returns.result import ResultE

from text_mate_backend.models.language_tool_models import LanguageToolResponse
from text_mate_backend.models.text_corretion_models import (
    CorrectionBlock,
    CorrectionResult,
    TextCorrectionOptions,
)
from text_mate_backend.services.language_tool_service import LanguageToolService
from text_mate_backend.utils.configuration import Configuration


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
    return blocks


@final
class TextCorrectionService:
    def __init__(self, config: Configuration, language_tool_Service: LanguageToolService) -> None:
        self.config = config
        self.language_tool = language_tool_Service

    def correct_text(self, text: str, options: TextCorrectionOptions) -> ResultE[CorrectionResult]:
        """Corrects the input text based on given options.
        Returns Either[str, str] where:
        - Left(str) contains error message
        - Right(str) contains corrected text
        """

        blocks: ResultE[list[CorrectionBlock]] = flow(
            text,
            self.language_tool.check_text,
            map_(_create_blocks),
        )

        return blocks.map(lambda blocks: CorrectionResult(blocks=blocks, original=text))
