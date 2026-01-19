from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration


async def rewrite(context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent) -> StreamingResponse:
    """
    Rewrites a given text based on provided context and options.

    Args:
        context: The QuickActionContext containing text and options
        config: Configuration containing LLM model and other settings
        llm_facade: The PydanticAIAgent instance to use for generating the response

    Returns:
        A StreamingResponse containing a rewritten version of the text
    """

    prompt = f"""
        You are an expert in rewriting text. Take a given text and rewrite
        it based on a provided options.
        Your task:
        1. Rewrite text based on provided options.
        2. The rewritten text should be in a same language as a input text.
        3. Provide only the rewritten text without any additional explanation or formatting.

        Text to be rewritten:
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
