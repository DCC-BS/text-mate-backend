from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.offical_letter import OFFICIAL_LETTER_NOTICE

MAIL_PROMPT = """
You are an assistant that helps to write emails.
Start the email with an appropriate greeting, followed by a clear and concise body that conveys the intended message.
End the email with a polite closing statement and your signature.
"""

OFFICIAL_LETTER_PROMPT = (
    """
You are an assistant that helps to write official letters. The written text should follow the guidelines probided here:
"""
    + OFFICIAL_LETTER_NOTICE
)

PRESENTATION_PROMPT = """
You are an assistant that helps to write presentations.
Begin with an engaging introduction that captures the audience's attention, followed by a series of well-organized points that support the main topic.
Conclude with a strong closing statement that reinforces the key message.
"""

REPORT_PROMPT = """
You are an assistant that helps to write reports.
Start with an executive summary that provides an overview of the report's purpose and findings, followed by detailed sections that present data and analysis.
End with a conclusion that summarizes the key insights and recommendations.
"""


def get_medium_prompt(option: str) -> str:
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
    Converts the given text into a formal or informal style based on the specified options.

    Args:
        text: The input text to be converted to formal or informal style
        config: Configuration containing LLM model and other settings
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the formal or informal version of the text
    """

    sys_prompt = get_medium_prompt(context.options)
    usr_prompt = context.text

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
