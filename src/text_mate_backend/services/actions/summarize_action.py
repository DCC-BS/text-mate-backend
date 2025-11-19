from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger("summarize_action")


# const items = computed<DropdownMenuItem[]>(() => [
#   { label: t('quick-actions.summarize.sentence'), value: 'sentence', icon: "i-lucide-tally-1" },
#   { label: t('quick-actions.summarize.three_sentence'), value: 'three_sentence', icon: "i-lucide-tally-3" },
#   { label: t('quick-actions.summarize.paragraph'), value: 'paragraph', icon: "i-lucide-text-wrap" },
#   { label: t('quick-actions.summarize.page'), value: 'page', icon: "i-lucide-file-text" },


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
            return "in one sentence"
        case "three_sentence":
            return "in three sentences"
        case "paragraph":
            return "in a single paragraph"
        case "page":
            return "in a single page"
        case "management_summary":
            return (
                "as a management summary. "
                "A management summary is a summary of the key points of the text for the management team. "
                "A management summary's length should be one paragraph up to a single page long, "
                "depending on the length of the text. "
                "Provide the management summary."
            )
        case _:
            logger.warning("Unknown summarize option, defaulting to concise manner", options=options)
            return "in a concise manner"


def summarize(context: QuickActionContext, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
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

    sys_prompt = PromptTemplate(
        """
        You are an assistant that summarizes text by extracting the key points and central message.
        Provide a summary {options} of the following text, capturing the main ideas and essential information.
        The summary should be in the same language as the input text.
        """
    ).format(options=format_options(context.options))
    usr_prompt: str = "Summarize the following text: " + context.text
    options: PromptOptions = PromptOptions(system_prompt=sys_prompt, user_prompt=usr_prompt, llm_model=config.llm_model)

    logger.debug("Created summarize prompt options")
    return run_prompt(
        options,
        llm_facade,
    )
