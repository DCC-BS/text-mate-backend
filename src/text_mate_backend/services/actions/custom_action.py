from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration


async def custom_prompt(
    context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent
) -> StreamingResponse:
    """
    Rewrites a given text according to a custom prompt.

    Args:
        context: The QuickActionContext containing input text and custom prompt/options
        config: Configuration containing LLM model and other settings
        llm_facade: The PydanticAIAgent instance to use for generating the response

    Returns:
        A StreamingResponse containing a rewritten version of the text
    """

    sys_prompt = f"""
        You are a writing assistant. Your task is to take a given prompt and rewrite text based on prompt.
        The rewritten text should be in a same language as a input text.
        {context.options}
        """

    usr_prompt = context.text

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    return await run_prompt(
        options,
        llm_facade,
    )
