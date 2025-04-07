import requests
from text_mate_backend.models.language_tool_models import LanguageToolResponse
from returns.result import safe
from text_mate_backend.utils.configuration import Configuration


class LanguageToolService:
    def __init__(self, config: Configuration) -> None:
        self.config = config

    @safe
    def check_text(self, text: str) -> LanguageToolResponse:
        """
        Check the text for spelling and grammar errors using LanguageTool API.
        """
        # call language tool api
        response = requests.post(
            f"{self.config.language_tool_api_url}/check",
            data={"text": text, "language": "auto", "preferredVariants": "de-CH", "level": "picky"},
        )

        # parse response
        return LanguageToolResponse(**response.json())
