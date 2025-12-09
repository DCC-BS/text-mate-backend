from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.emails import EMAIL_PROMPT_TEMPLATE
from text_mate_backend.utils.offical_letter import OFFICIAL_LETTER_NOTICE

MAIL_PROMPT = (
    """
You are an assistant that helps to write emails. The written email should follow the guidelines provided here: {EMAIL_PROMPT}
The text should be in the same language as the input text.
"""  # noqa: E501
).format(EMAIL_PROMPT=EMAIL_PROMPT_TEMPLATE)

OFFICIAL_LETTER_PROMPT = (
    """
You are an assistant that helps to write official letters. The written text should follow the guidelines provided here: {OFFICIAL_LETTER_NOTICE}
The text should be in the same language as the input text.
"""  # noqa: E501
).format(OFFICIAL_LETTER_NOTICE=OFFICIAL_LETTER_NOTICE)

PRESENTATION_PROMPT = """
You are an assistant that helps to write presentations.
Begin with an engaging introduction that captures the audience's attention, followed by a series of well-organized points that support the main topic.
Conclude with a strong closing statement that reinforces the key message.
The text should be in the same language as the input text.
"""  # noqa: E501

REPORT_PROMPT = """
You are an assistant that helps to write reports.
Start with an executive summary that provides an overview of the report's purpose and findings, followed by detailed sections that present data and analysis.
End with a conclusion that summarizes the key insights and recommendations.
The text should be in the same language as the input text.
"""  # noqa: E501


def get_medium_prompt(option: str) -> str:
    """
    Selects the prompt template corresponding to a specified output medium.

    Parameters:
        option (str): Medium identifier; must be one of "email", "official_letter", "presentation", or "report".

    Returns:
        str: The prompt template string for the requested medium.

    Raises:
        ValueError: If `option` is not a supported medium identifier.
    """
    if option == "email":
        return MAIL_PROMPT
    elif option == "official_letter":
        return OFFICIAL_LETTER_PROMPT
    elif option == "presentation":
        return PRESENTATION_PROMPT
    elif option == "report":
        return REPORT_PROMPT
    else:
        raise ValueError(f"Unsupported medium option: {option}")


def medium(context: QuickActionContext, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Rewrites the given text for a specific medium (e.g. email, official letter, presentation, report).

    Args:
        context: QuickActionContext containing the input text and the medium option
        config: Configuration containing LLM model and other settings
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the rewritten version of the text for the specific medium
    """

    sys_prompt = get_medium_prompt(context.options)
    usr_prompt = context.text

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
