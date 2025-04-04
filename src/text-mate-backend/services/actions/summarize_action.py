from openai import OpenAI

from services.actions.action_utils import PrompOptions, run_prompt


def summarize(text: str, llm: OpenAI):
    """
    Summarizes the given text by providing a condensed version that captures the main points.
    """

    options = PrompOptions(
        system_prompt="You are an assistant that summarizes text by extracting the key points and central message.",
        user_prompt=f'Provide a summary of the following text, capturing the main ideas and essential information: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
