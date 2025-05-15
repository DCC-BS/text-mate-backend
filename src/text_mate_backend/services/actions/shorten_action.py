from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade


def shorten(text: str, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Shortens the given text while preserving its key meaning and content.

    Args:
        text: The input text to be shortened
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the shortened version of the text
    """

    prompt = PromptTemplate(
        """
        You are an assistant that shortens text while preserving its key meaning and content.
        Shorten the following text in a concise way while preserving the main points:

        # START TEXT #
        {text}
        # END TEXT #
        """
    ).format(text=text)

    options: PromptOptions = PromptOptions(prompt=prompt)

    return run_prompt(
        options,
        llm_facade,
    )
