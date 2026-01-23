from abc import abstractmethod
from typing import override

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_utils import get_language_instruction
from text_mate_backend.agents.base import BaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration


class QuickActionBaseAgent(BaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config, deps_type=QuickActionContext, output_type=str)

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

                - Format the text as markdown, don't use any html tags.
                - Don't include any introductory or closing remarks.
                - Answer in the same language as the input text.
                - Only respond with the answer, do not add any other text.
                - Don't add any extra information or context.
                - Don't add any whitespaces.
                """

        return agent
