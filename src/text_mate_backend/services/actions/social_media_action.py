from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration

async def social_mediafy(context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent) -> StreamingResponse:
    """
    Converts a given text into a social media post by adding emojis and hashtags.

    Args:
        context: The QuickActionContext containing the text and options
        config: Configuration containing LLM model and other settings
        llm_facade: The PydanticAIAgent instance to use for generating the response

    Returns:
        A StreamingResponse containing a social media version of the text
    """
    sys_prompt = f"""
        You are a social media expert. Your task is to turn text into social media text.
        Use emojis and hashtags if appropriate for the platform.
        The text should be in the same language as the input text.
        Turn the following text into a text for social media for {context.options}:
        """

    usr_prompt = context.text

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    return await run_prompt(
        options,
        llm_facade,
    )
