from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration


async def bullet_points(
    context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent
) -> StreamingResponse:
    """
    Converts a given text into a structured bullet point format with key points.

    Args:
        context: QuickActionContext containing input text and bullet points option
        config: Configuration containing LLM model and other settings
        llm_facade: The PydanticAIAgent instance to use for generating the response

    Returns:
        A StreamingResponse containing bullet points version of text
    """

    sys_prompt = """
        You are an assistant that converts text into a well-structured bullet point format.
        Extract and highlight key points from text.

        Convert to following text into a structured bullet point format.
        Identify and organize main ideas and supporting points.
        The bullet points should be in the same language as the input text.
        Use markdown formatting for bullet points.
        """

    usr_propt = context.text

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_propt, llm_model=config.llm_model)

    return await run_prompt(
        options,
        llm_facade,
    )
