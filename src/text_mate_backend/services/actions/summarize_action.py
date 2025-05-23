from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("summarize_action")


def summarize(text: str, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Summarizes the given text by providing a condensed version that captures main points.

    Args:
        text: The input text to be summarized
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the summarized version of the text
    """
    text_length = len(text)
    logger.info("Processing summarize request", text_length=text_length)

    if text_length < 50:
        logger.warning("Text may be too short for effective summarization", text_length=text_length)

    prompt = PromptTemplate(
        """
        You are an assistant that summarizes text by extracting the key points and central message.
        Provide a summary of the following text, capturing the main ideas and essential information:

        # START TEXT #
        {text}
        # END TEXT #
        """
    ).format(text=text)

    options: PromptOptions = PromptOptions(prompt=prompt)

    logger.debug("Created summarize prompt options")
    return run_prompt(
        options,
        llm_facade,
    )
