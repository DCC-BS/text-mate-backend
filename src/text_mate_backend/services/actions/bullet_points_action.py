from fastapi.responses import StreamingResponse

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade


def bullet_points(text: str, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Converts the given text into a structured bullet point format with key points.

    Args:
        text: The input text to be converted to bullet points
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse containing the bullet points version of the text
    """

    options: PromptOptions = PromptOptions(
        system_prompt="You are an assistant that converts text into a well-structured bullet point format. Extract and highlight the key points from the text.",
        user_prompt=f'Convert the following text into a structured bullet point format. Identify and organize the main ideas and supporting points: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm_facade,
    )
