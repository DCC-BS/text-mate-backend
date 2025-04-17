from fastapi.responses import StreamingResponse
from openai import OpenAI

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.utils.logger import get_logger

logger = get_logger("translate_action")


def translate(text: str, language: str, llm: OpenAI) -> StreamingResponse:
    """
    Translates the given text into the specified language.

    Args:
        text: The text to translate
        language: The target language for translation
        llm: OpenAI client instance

    Returns:
        StreamingResponse: A streaming response containing the translated text
    """
    text_length = len(text)
    logger.info("Processing translate request", text_length=text_length)

    options: PromptOptions = PromptOptions(
        system_prompt="You are a professional translator.",
        user_prompt=f'Translate the following text into {language}: "{text}"',
        temperature=0.7,
    )

    logger.debug("Created translate prompt options")
    return run_prompt(
        options,
        llm,
    )
