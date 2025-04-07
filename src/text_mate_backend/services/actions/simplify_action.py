from fastapi.responses import StreamingResponse
from openai import OpenAI

from text_mate_backend.services.actions.action_utils import PrompOptions, run_prompt


def simplify(text: str, llm: OpenAI) -> StreamingResponse:
    """
    Simplifies the given text by removing complex words and phrases.

    Args:
        text: The input text to be simplified
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse containing the simplified version of the text
    """

    options: PrompOptions = PrompOptions(
        system_prompt="You are an assistant that simplifies text.",
        user_prompt=f'Simplify the following text: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
