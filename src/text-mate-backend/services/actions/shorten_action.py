from openai import OpenAI

from services.actions.action_utils import PrompOptions, run_prompt


def shorten(text: str, llm: OpenAI):
    """
    Shortens the given text while preserving its key meaning and content.
    """

    options = PrompOptions(
        system_prompt="You are an assistant that shortens text while preserving its key meaning and content.",
        user_prompt=f'Shorten the following text in a concise way while preserving the main points: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
