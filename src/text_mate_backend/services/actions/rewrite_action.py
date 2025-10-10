from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration


def rewrite(context: QuickActionContext, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Rewrites the given text based on provided context and options.

    Args:
        context: The QuickActionContext containing text and options
        config: Configuration containing LLM model and other settings
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the rewritten version of the text
    """

    prompt = PromptTemplate(
        """
        You are an expert in rewriting text. Take the given text and rewrite
        it based on the provided options.
        Your task:
        1. Rewrite the text based on the provided options.
        2. The rewritten text should be in the same language as the input text.
        3. Provide only the rewritten text without any additional explanation or formatting.

        Text to be rewritten:
        # START TEXT #
        {text}
        # END TEXT #

        # START OPTIONS #
        {options}
        # END OPTIONS #
        """
    ).format(text=context.text, options=context.options)

    options: PromptOptions = PromptOptions(prompt=prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
