from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration


def bullet_points(context: QuickActionContext, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Converts the given text into a structured bullet point format with key points.

    Args:
        context: QuickActionContext containing the input text and the bullet points option
        config: Configuration containing LLM model and other settings
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the bullet points version of the text
    """

    sys_prompt = """
        You are an assistant that converts text into a well-structured bullet point format.
        Extract and highlight the key points from the text.

        Convert the following text into a structured bullet point format.
        Identify and organize the main ideas and supporting points.
        The bullet points should be in the same language as the input text.
        Use markdown formatting for the bullet points.
        """

    usr_propt = context.text

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_propt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
