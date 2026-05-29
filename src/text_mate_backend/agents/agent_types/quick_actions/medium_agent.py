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
Du bist ein Assistent, der beim Schreiben von E-Mails hilft. Die E-Mail soll den folgenden Richtlinien folgen: {EMAIL_PROMPT}
1. Rufe zuerst das Tool get_current_user auf, um die Benutzerdaten abzurufen.
2. Schreibe die E-Mail und verwende den Vornamen und Nachnamen der Benutzerin oder des Benutzers in der Signatur. Verwende für die Anrede einen Platzhalter.
"""  # noqa: E501
).format(EMAIL_PROMPT=EMAIL_PROMPT_TEMPLATE)

OFFICIAL_LETTER_PROMPT = (
    """
Du bist ein Assistent, der beim Schreiben von Behördenbriefen hilft. Der Text soll den folgenden Richtlinien folgen: {OFFICIAL_LETTER_NOTICE}.
"""  # noqa: E501
).format(OFFICIAL_LETTER_NOTICE=OFFICIAL_LETTER_NOTICE)

PRESENTATION_PROMPT = """
Du bist ein Assistent, der beim Schreiben von Präsentationen hilft.
Beginne mit einer fesselnden Einleitung, die die Aufmerksamkeit des Publikums weckt,
gefolgt von einer Reihe gut strukturierter Punkte, die das Hauptthema stützen.
Schliesse mit einer starken Schlussaussage, die die Kernbotschaft verstärkt.
"""  # noqa: E501

REPORT_PROMPT = """
Du bist ein Assistent, der beim Schreiben von Berichten hilft.
Beginne mit einer Management Summary, die Zweck und Ergebnisse des Berichts überblicksartig darstellt,
gefolgt von ausführlichen Abschnitten mit Daten und Analyse.
Schliesse mit einem Fazit, das die wichtigsten Erkenntnisse und Empfehlungen zusammenfasst.
"""  # noqa: E501


class MediumAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config, enable_thinking=False)

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
