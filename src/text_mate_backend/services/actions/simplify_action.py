from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration

async def simplify(context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent) -> StreamingResponse:
    """
    Simplifies a given text by removing complex words and phrases.

    Args:
        context: The QuickActionContext containing the text and options
        config: Configuration containing LLM model and other settings
        llm_facade: The PydanticAIAgent instance to use for generating the response

    Returns:
        A StreamingResponse containing a simplified version of the text
    """

    prompt = f"""
        You are an assistant that simplifies text.
        Simplify the following text:

        # START TEXT #
        {context.text}
        # END TEXT #

        # START OPTIONS #
        {context.options}
        # END OPTIONS #
        """

    options: PromptOptions = PromptOptions(user_prompt=prompt, llm_model=config.llm_model)

    return await run_prompt(
        options,
        llm_facade,
    )
