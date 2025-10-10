from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.easy_language import CLAUDE_TEMPLATE_LS, REWRITE_COMPLETE, RULES_LS, SYSTEM_MESSAGE_LS


def plain_language(context: QuickActionContext, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Converts the given text into plain language (Leichte Sprache) with A2-A1 language level.

    Args:
        context: The QuickActionContext containing text and options
        config: Configuration containing LLM model and other settings
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the plain language version of the text
    """

    # Create a modified template that includes options
    template_with_options = SYSTEM_MESSAGE_LS + CLAUDE_TEMPLATE_LS

    prompt = PromptTemplate(template_with_options).format(
        prompt=context.text, completeness=REWRITE_COMPLETE, rules=RULES_LS, options=context.options
    )

    options: PromptOptions = PromptOptions(prompt=prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
