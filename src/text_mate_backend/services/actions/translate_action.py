from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("translate_action")


def translate(text: str, language: str, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Translates the given text into the specified language.

    Args:
        text: The text to translate
        language: The target language for translation
        llm_facade: LLMFacade instance

    Returns:
        StreamingResponse: A streaming response containing the translated text
    """
    text_length = len(text)
    logger.info("Processing translate request", text_length=text_length)

    prompt = PromptTemplate(
        """
        You are a professional translator.
        Translate the following text into {language}:

        # START TEXT #
        {text}
        # END TEXT #
        """
    ).format(text=text, language=language)

    options: PromptOptions = PromptOptions(prompt=prompt)

    logger.debug("Created translate prompt options")
    return run_prompt(
        options,
        llm_facade,
    )
