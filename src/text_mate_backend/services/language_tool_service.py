import time
from urllib.parse import urlparse

import requests
from dcc_backend_common.logger import get_logger
from returns.result import safe

from text_mate_backend.models.error_codes import LANGUAGE_TOOL_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.language_tool_models import LanguageToolResponse
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("language_tool_service")


class LanguageToolService:
    def __init__(self, config: Configuration) -> None:
        self.config = config
        api_url = self.config.language_tool_api_url
        parsed_url = urlparse(api_url)
        host = parsed_url.netloc or parsed_url.path  # Use path if netloc is empty
        logger.info("LanguageToolService initialized", api_host=host)

    @safe
    def check_text(self, language: str, text: str) -> LanguageToolResponse:
        """
        Check the text for spelling and grammar errors using LanguageTool API.

        Args:
            text: The text to check for errors

        Returns:
            LanguageToolResponse object with the results from the API

        Raises:
            Exception: If there's an API error or connection issue
        """
        text_length = len(text)
        text_preview = text[:50] + ("..." if text_length > 50 else "")

        logger.debug("Text preview", preview=text_preview)

        start_time = time.time()
        try:
            preferedVariants = get_preferred_variants(language)
            # call language tool api
            response = requests.post(
                f"{self.config.language_tool_api_url}/check",
                data={"text": text, "language": language, "preferredVariants": preferedVariants, "level": "picky"},
            )

            response.raise_for_status()  # Raise exception for 4XX/5XX responses

            # parse response
            response_data = response.json()

            return LanguageToolResponse(**response_data)

        except requests.exceptions.RequestException as e:
            logger.error(
                "LanguageTool API request failed",
                error=str(e),
                text=e.response.text if hasattr(e, "response") and e.response is not None else None,
                error_type=type(e).__name__,
                response_time_ms=round((time.time() - start_time) * 1000),
            )

            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": LANGUAGE_TOOL_ERROR,
                    "debugMessage": str(e),
                }
            ) from e


def get_preferred_variants(language: str) -> str | None:
    match language:
        case "auto":
            return "de-CH"
        case _:
            return None
