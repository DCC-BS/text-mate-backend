from fastapi.responses import StreamingResponse
from openai import OpenAI

from text_mate_backend.services.actions.action_utils import PrompOptions, run_prompt


def summarize(text: str, llm: OpenAI) -> StreamingResponse:
    """
    Summarizes the given text by providing a condensed version that capturese main points.

    Args:
        text: The input text to be summarized
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse containing the summarized version of the text
    """

    options: PrompOptions = PrompOptions(
        system_prompt="You are an assistant that summarizes text by extracting the key points and central message.",
        user_prompt=f'Provide a summary of the following text, capturing the main ideas and essential information: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
