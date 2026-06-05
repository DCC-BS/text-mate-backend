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
            return "Die Zusammenfassung soll genau einen Satz lang sein."
        case "three_sentence":
            return "Die Zusammenfassung soll genau drei Sätze lang sein."
        case "paragraph":
            return "Die Zusammenfassung soll genau einen Abschnitt lang sein."
        case "page":
            return "Die Zusammenfassung soll höchstens eine Seite lang sein."
        case "management_summary":
            return (
                "als Management Summary. "
                "Ein Management Summary fasst die wichtigsten Punkte eines Textes für die Geschäftsleitung zusammen. "
                "Ein Management Summary ist je nach Länge des Textes einen Abschnitt bis eine Seite lang."
            )
        case _:
            logger.warning("Unknown summarize option, defaulting to concise manner", extra={"options": options})
            return "in knapper Form."


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
        Du bist ein Assistent, der Texte zusammenfasst, indem du die Kernpunkte und die zentrale Aussage herausarbeitest.
        Fasse den folgenden Text zusammen und erfasse dabei die Hauptgedanken und die wesentlichen Informationen.
        Das sind die Anforderungen an die Zusammenfassung: {format_options(ctx.deps.options)}
        """
