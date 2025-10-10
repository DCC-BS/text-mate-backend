from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration


def social_mediafy(context: QuickActionContext, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Converts the given text into a social media post by adding emojis and hashtags.

    Args:
        context: The QuickActionContext containing text and options
        config: Configuration containing LLM model and other settings
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

        # START OPTIONS #
        {options}
        # END OPTIONS #
        """
    ).format(text=context.text, options=context.options)

    options: PromptOptions = PromptOptions(prompt=prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
