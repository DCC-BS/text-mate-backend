from typing import override

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_types.quick_actions.quick_action_base_agent import QuickActionBaseAgent
from text_mate_backend.models.quick_actions_models import CurrentUser, QuickActionContext
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.emails import EMAIL_PROMPT_TEMPLATE
from text_mate_backend.utils.offical_letter import OFFICIAL_LETTER_NOTICE

MAIL_PROMPT = (
    """
You are an assistant that helps to write emails. The written email should follow the guidelines provided here: {EMAIL_PROMPT}
1. First call get_current_user tool for retrieving the user data.
2. Write the email using the user's given name and family in the sigiture for the greeting use a placeholder.
"""  # noqa: E501
).format(EMAIL_PROMPT=EMAIL_PROMPT_TEMPLATE)

OFFICIAL_LETTER_PROMPT = (
    """
You are an assistant that helps to write official letters. The written text should follow the guidelines provided here: {OFFICIAL_LETTER_NOTICE}.
"""  # noqa: E501
).format(OFFICIAL_LETTER_NOTICE=OFFICIAL_LETTER_NOTICE)

PRESENTATION_PROMPT = """
You are an assistant that helps to write presentations.
Begin with an engaging introduction that captures the audience's attention,
followed by a series of well-organized points that support the main topic.
Conclude with a strong closing statement that reinforces the key message.
"""  # noqa: E501

REPORT_PROMPT = """
You are an assistant that helps to write reports.
Start with an executive summary that provides an overview of the report's purpose and findings,
followed by detailed sections that present data and analysis.
End with a conclusion that summarizes the key insights and recommendations.
"""  # noqa: E501


class MediumAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_agent(self, model: Model) -> Agent[QuickActionContext, str]:
        agent = super().create_agent(model)
        agent.end_strategy = "exhaustive"

        @agent.tool
        def get_current_user(ctx: RunContext[QuickActionContext[CurrentUser]]):
            """
            Get info about the user name.
            """
            extras = ctx.deps.extras
            if extras is None:
                return {
                    "given_name": "",
                    "family_name": "",
                    "email": "",
                }
            return {
                "given_name": extras["given_name"],
                "family_name": extras["family_name"],
                "email": extras["email"],
            }

        return agent

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        option = ctx.deps.options

        if option == "email":
            return MAIL_PROMPT
        elif option == "official_letter":
            return OFFICIAL_LETTER_PROMPT
        elif option == "presentation":
            return PRESENTATION_PROMPT
        elif option == "report":
            return REPORT_PROMPT
        else:
            raise ValueError(f"Unsupported medium option: {option}")
