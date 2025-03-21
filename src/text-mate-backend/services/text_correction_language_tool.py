from typing import final

import requests
from functional_monads.either import Either, right

from models.language_tool_models import LanguageToolResponse
from models.text_corretion_models import (
    CorrectionBlock,
    CorrectionResult,
    TextCorrectionOptions,
)
from utils.configuration import config


@final
class TextCorrectionService:
    def correct_text(self, text: str, options: TextCorrectionOptions) -> Either[str, CorrectionResult]:
        """Corrects the input text based on given options.
        Returns Either[str, str] where:
        - Left(str) contains error message
        - Right(str) contains corrected text
        """

        # call language tool api
        response = requests.post(
            f"{config.language_tool_api_url}/check",
            data={"text": text, "language": "auto", "preferredVariants": "de-CH", "level": "picky"},
        )

        # parse response
        language_tool_response = LanguageToolResponse(**response.json())

        # create correction blocks
        blocks = []
        for match in language_tool_response.matches:
            blocks.append(
                CorrectionBlock(
                    original=match.context.text[match.context.offset : match.context.offset + match.context.length],
                    corrected=list(map(lambda replacement: replacement.value, match.replacements)),
                    explanation=match.message,
                    offset=match.offset,
                    length=match.length,
                )
            )

        return right(CorrectionResult(blocks=blocks, original=text))
