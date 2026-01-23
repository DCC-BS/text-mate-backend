import json
from typing import List

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.base import BaseAgent
from text_mate_backend.models.rule_models import Rule, RulesValidationContainer
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """ You are an expert in editorial guidelines. Review only the given rules and
                identify any clear, material violations in the input text.
                Guidelines:
                1. Focus on substantive issues that meaningfully impact clarity, accuracy, tone, wrong use of words,
                abbreviations, etc.
                2. If you are unsure whether a rule is violated, do not report it.
                3. Provide practical, respectful rewrite proposals that keep the author's intent.
                4. If no qualifying violations exist, return an empty list.

                Rules documentation:
                ---------------
                {rules}
                ---------------

                Keep your answer in the original language."""


class AdvisorAgent(BaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config, deps_type=list[Rule], output_type=RulesValidationContainer, enable_thinking=True)

    def create_agent(self, model: Model):
        agent = Agent(model=model, deps_type=List[Rule], output_type=RulesValidationContainer)

        @agent.instructions
        def get_instruction(ctx: RunContext[List[Rule]]):
            return INSTRUCTION.format(rules=json.dumps(ctx.deps))

        return agent
