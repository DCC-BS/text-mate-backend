from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration


def simplify(text: str, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Simplifies the given text by removing complex words and phrases.

    Args:
        text: The input text to be simplified
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the simplified version of the text
    """

    prompt = PromptTemplate(
        """
        You are an assistant that simplifies text.
        Simplify the following text:

        # START TEXT #
        {text}
        # END TEXT #
        """
    ).format(text=text)

    options: PromptOptions = PromptOptions(prompt=prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
