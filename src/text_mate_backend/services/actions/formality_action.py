from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration


async def formality(
    context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent
) -> StreamingResponse:
    """
    Converts a given text into a formal or informal style based on specified options.

    Args:
        text: The input text to be converted to formal or informal style
        config: Configuration containing LLM model and other settings
        llm_facade: The PydanticAIAgent instance to use for generating the response

    Returns:
        A StreamingResponse containing a formal or informal version of the text
    """

    sys_prompt = f"""
        You are a writing expert.
        We want to transform a formality of text.
        Your task is to take a given text and convert it into a {context.options} text.
        Keep a original meaning.
        The rewritten text should be in a same language as a input text.
        """

    usr_prompt = context.text

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    return await run_prompt(
        options,
        llm_facade,
    )
