from openai import OpenAI

from services.actions.action_utils import PrompOptions, run_prompt


def social_mediafy(text: str, llm: OpenAI):
    """
    Converts the given text into a social media post by adding emojis and hashtags.
    """

    options = PrompOptions(
        system_prompt="You are an assistant that turns text into social media text. Use emojis and hashtags.",
        user_prompt=f'Turn the the following text into a text for social media: "{text}"',
        temperature=0.7,
    )

    return run_prompt(
        options,
        llm,
    )
