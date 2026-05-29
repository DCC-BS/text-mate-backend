from abc import abstractmethod
from typing import override

from dcc_backend_common.llm_agent import BaseAgent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_utils import get_language_instruction
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration


class QuickActionBaseAgent(BaseAgent):
    def __init__(self, config: Configuration, enable_thinking: bool = False):
        super().__init__(config, deps_type=QuickActionContext, output_type=str, enable_thinking=enable_thinking)

    @abstractmethod
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str: ...

    @override
    def create_agent(self, model: Model) -> Agent[QuickActionContext, str]:
        agent = Agent(model=model, deps_type=QuickActionContext)

        @agent.instructions
        def create_instruction(ctx: RunContext[QuickActionContext]):
            return f"""
                {self.create_instruction(ctx)}

                {get_language_instruction(ctx.deps.language)}

                Halte dich strikt an diese Ausgaberegeln:
                - Gib nur reinen Text aus, keine HTML-Tags und kein Markdown.
                - Gib keine Einleitung und keinen Schlusskommentar aus.
                - Gib ausschliesslich das Ergebnis aus, keinen weiteren Text.
                - Füge keine zusätzlichen Informationen oder Erklärungen hinzu.
                """

        return agent
