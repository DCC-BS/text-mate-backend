from fastapi.responses import StreamingResponse

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade


def shorten(text: str, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Shortens the given text while preserving its key meaning and content.

    Args:
        text: The input text to be shortened
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse containing the shortened version of the text
    """

    options: PromptOptions = PromptOptions(
        system_prompt="You are an assistant that shortens text while preserving its key meaning and content.",
        user_prompt=f'Shorten the following text in a concise way while preserving the main points: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm_facade,
    )
