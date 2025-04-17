from fastapi.responses import StreamingResponse
from openai import OpenAI

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt


def social_mediafy(text: str, llm: OpenAI) -> StreamingResponse:
    """
    Converts the given text into a social media post by adding emojis and hashtags.

    Args:
        text: The input text to be converted into social media format
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse containing the social media version of the text
    """

    options: PromptOptions = PromptOptions(
        system_prompt="You are an assistant that turns text into social media text. Use emojis and hashtags.",
        user_prompt=f'Turn the the following text into a text for social media: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
