from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade


def social_mediafy(text: str, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Converts the given text into a social media post by adding emojis and hashtags.

    Args:
        text: The input text to be converted into social media format
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the social media version of the text
    """

    prompt = PromptTemplate(
        """
        You are an assistant that turns text into social media text. Use emojis and hashtags.
        Turn the following text into a text for social media:

        # START TEXT #
        {text}
        # END TEXT #
        """
    ).format(text=text)

    options: PromptOptions = PromptOptions(prompt=prompt)

    return run_prompt(
        options,
        llm_facade,
    )
