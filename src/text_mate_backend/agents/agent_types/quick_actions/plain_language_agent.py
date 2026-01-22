"""Plain language agent for converting text to simple language."""

from typing import final, override

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.agents.base import UserPrompt
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.easy_language import CLAUDE_TEMPLATE_LS, REWRITE_COMPLETE, RULES_LS, SYSTEM_MESSAGE_LS


@final
class PlainLanguageAgent(QuickActionBaseAgent):
    """Agent for converting text to plain language (Leichte Sprache)."""

    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_agent(self, model: Model) -> Agent[QuickActionContext, str]:
        agent = super().create_agent(model)

        @agent.tool
        async def check_readability_score(ctx: RunContext[QuickActionContext], text: str) -> dict:
            """Calculate basic readability metrics."""
            words = text.split()
            sentences = [s.strip() for s in text.split(".") if s.strip()]
            avg_word_length = sum(len(w) for w in words) / max(len(words), 1)
            avg_sentence_length = len(words) / max(len(sentences), 1)

            return {
                "word_count": len(words),
                "sentence_count": len(sentences),
                "avg_word_length": round(avg_word_length, 2),
                "avg_sentence_length": round(avg_sentence_length, 2),
            }

        return agent

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        return SYSTEM_MESSAGE_LS

    @override
    def process_prompt(self, prompt: UserPrompt, deps: QuickActionContext):
        usr_prompt = CLAUDE_TEMPLATE_LS.format(prompt=prompt, completeness=REWRITE_COMPLETE, rules=RULES_LS)

        return super().process_prompt(usr_prompt, deps)
