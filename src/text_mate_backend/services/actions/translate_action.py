from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger("translate_action")


def translate(
    context: QuickActionContext, language: str, config: Configuration, llm_facade: LLMFacade
) -> StreamingResponse:
    """
    Translates the given text into the specified language.

    Args:
        context: The QuickActionContext containing text and options
        language: The target language for translation
        config: Configuration containing LLM model and other settings
        llm_facade: LLMFacade instance

    Returns:
        StreamingResponse: A streaming response containing the translated text
    """
    prompt = PromptTemplate(
        """
        You are a professional translator.
        Translate the following text into {language}:

        # START TEXT #
        {text}
        # END TEXT #

        # START OPTIONS #
        {options}
        # END OPTIONS #
        """
    ).format(text=context.text, language=language, options=context.options)

    options: PromptOptions = PromptOptions(user_prompt=prompt, llm_model=config.llm_model)

    logger.debug("Created translate prompt options")
    return run_prompt(
        options,
        llm_facade,
    )
