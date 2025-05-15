from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade


def bullet_points(text: str, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Converts the given text into a structured bullet point format with key points.

    Args:
        text: The input text to be converted to bullet points
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse containing the bullet points version of the text
    """

    prompt = PromptTemplate(
        """
        You are an assistant that converts text into a well-structured bullet point format.
        Extract and highlight the key points from the text.

        Convert the following text into a structured bullet point format.
        Identify and organize the main ideas and supporting points.

        # START TEXT #
        {text}
        # END TEXT #
        """
    ).format(text=text)

    options: PromptOptions = PromptOptions(prompt=prompt)

    return run_prompt(
        options,
        llm_facade,
    )
