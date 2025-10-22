from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration


def formality(context: QuickActionContext, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Converts the given text into a formal or informal style based on the specified options.

    Args:
        text: The input text to be converted to formal or informal style
        config: Configuration containing LLM model and other settings
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the formal or informal version of the text
    """

    sys_prompt = """
        You are an assistant that converts text into a {option} text. Try to keept the original meaning.
        """

    usr_prompt = context.text

    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
