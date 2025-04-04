from openai import OpenAI

from services.actions.action_utils import PrompOptions, run_prompt


def bullet_points(text: str, llm: OpenAI):
    """
    Converts the given text into a structured bullet point format with key points.
    """

    options = PrompOptions(
        system_prompt="You are an assistant that converts text into a well-structured bullet point format. Extract and highlight the key points from the text.",
        user_prompt=f'Convert the following text into a structured bullet point format. Identify and organize the main ideas and supporting points: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
