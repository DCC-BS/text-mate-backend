import re
from typing import override

from dcc_backend_common.logger import get_logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration

logger = get_logger()


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
            logger.warning("Unknown summarize option, defaulting to concise manner", extra={"options": options})
            return "in a concise manner"


class SummarizeAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_agent(self, model: Model) -> Agent[QuickActionContext, str]:
        agent = super().create_agent(model)

        @agent.tool_plain
        def count_sentences(text: str) -> int:
            """Count sentences in the given text."""
            return len([s for s in re.split(r"[.!?]+", text) if s.strip()])

        @agent.tool_plain
        def count_paragraphs(text: str) -> int:
            """Count paragraphs in the given text."""
            return len([p for p in re.split(r"\n\s*\n", text) if p.strip()])

        @agent.tool_plain
        def count_pages(text: str) -> float:
            """Estimate page count based on character count (3000 chars per page)."""
            return len(text) / 3000

        return agent

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        return f"""
        You are an assistant that summarizes text by extracting the key points and central message.
        Provide a summary of the following text, capturing the main ideas and essential information.
        Those are the requirements for the summary: {format_options(ctx.deps.options)}
        """
