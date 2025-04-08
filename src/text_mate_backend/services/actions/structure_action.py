from fastapi.responses import StreamingResponse
from openai import OpenAI

from text_mate_backend.services.actions.action_utils import PrompOptions, run_prompt


def structure_text(text: str, llm: OpenAI) -> StreamingResponse:
    """
    Converts the given text into a social media post by adding emojis and hashtags.

    Args:
        text: The input text to be converted into social media format
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse containing the social media version of the text
    """

    options: PrompOptions = PrompOptions(
        system_prompt="You are an assistant that structures text.",
        user_prompt=f'Structure the follwing text: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
