from openai import OpenAI

from services.actions.action_utils import PrompOptions, run_prompt


def simplify(text: str, llm: OpenAI):
    """
    Simplifies the given text by removing complex words and phrases.
    """

    options = PrompOptions(
        system_prompt="You are an assistant that simplifies text.",
        user_prompt=f'Simplify the following text: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
