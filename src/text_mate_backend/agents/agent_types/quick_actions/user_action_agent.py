from typing import override

from pydantic_ai import RunContext

from text_mate_backend.agents import QuickActionBaseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.models.user_action_models import UserAction
from text_mate_backend.utils.configuration import Configuration


class UserActionAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext[UserAction]]):
        if ctx.deps.extras is None:
            raise ValueError("UserActionAgent: extras is None")

        return ctx.deps.extras.content
