from dcc_backend_common.logger import get_logger
from fastapi.responses import StreamingResponse

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("summarize_action")


def format_options(options: str) -> str:
    """
    Formats the options string for inclusion in the prompt.

    Args:
        options: The raw options string

    Returns:
        A formatted options string
    """
    match options.lower().strip():
        case "sentence":
            return "The summary should be exactly one sentence long."
        case "three_sentence":
            return "The summary should be exactly three sentences long."
        case "paragraph":
            return "The summary should be one paragraph long."
        case "page":
            return "The summary should be up to one page long."
        case "management_summary":
            return (
                "as a management summary. "
                "A management summary is a summary of the key points of a text for the management team. "
                "A management summary's length should be one paragraph up to one page long, "
                "depending on the length of the text. "
            )
        case _:
            logger.warning("Unknown summarize option, defaulting to concise manner", options=options)
            return "in a concise manner"


async def summarize(
    context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent
) -> StreamingResponse:
    """
    Summarizes the given text by providing a condensed version that captures main points.

    Args:
        context: The QuickActionContext containing text and options
        config: Configuration containing LLM model and other settings
        llm_facade: The LLMFacade instance to use for generating the response

    Returns:
        A StreamingResponse containing the summarized version of the text
    """
    text_length = len(context.text)

    if text_length < 50:
        logger.warning("Text may be too short for effective summarization", text_length=text_length)

    sys_prompt = f"""
        You are an assistant that summarizes text by extracting the key points and central message.
        Provide a summary of the following text, capturing the main ideas and essential information.
        The summary should be in the same language as the input text.
        Those are the requirements for the summary: {format_options(context.options)}
        """

    options: PromptOptions = PromptOptions(
        system_prompt=sys_prompt, user_prompt=context.text, llm_model=config.llm_model
    )

    logger.debug("Created summarize prompt options")
    return await run_prompt(
        options,
        llm_facade,
    )
