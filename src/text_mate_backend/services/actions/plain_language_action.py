from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.easy_language import CLAUDE_TEMPLATE_LS, REWRITE_COMPLETE, RULES_LS, SYSTEM_MESSAGE_LS

async def plain_language(context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent) -> StreamingResponse:
    """
    Converts a given text into plain language (Leichte Sprache) with A2-A1 language level.

    Args:
        context: The QuickActionContext containing the text
        config: Configuration containing LLM model and other settings
        llm_facade: The PydanticAIAgent instance to use for generating the response

    Returns:
        A StreamingResponse containing a plain language version of the text
    """

    # Create a modified template that includes options
    sys_prompt = SYSTEM_MESSAGE_LS

    usr_prompt = CLAUDE_TEMPLATE_LS.format(
        prompt=context.text, completeness=REWRITE_COMPLETE, rules=RULES_LS
    )

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    return await run_prompt(
        options,
        llm_facade,
    )

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
