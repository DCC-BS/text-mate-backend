from dcc_backend_common.llm_agent import BaseAgent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.models.rule_models import RulesContainer, RulesValidationResult
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """ Du bist ein Experte für Redaktionsrichtlinien. Prüfe ausschliesslich anhand der
                gegebenen Regeln und finde klare, wesentliche Verstösse im Eingabetext.
                Richtlinien:
                1. Konzentriere dich auf wesentliche Probleme, die Klarheit, Korrektheit, Ton, falsche
                Wortwahl, Abkürzungen usw. spürbar beeinträchtigen.
                2. Bist du unsicher, ob eine Regel verletzt ist, melde sie nicht.
                3. Mache praktische, respektvolle Verbesserungsvorschläge, die die Absicht der Autorin
                oder des Autors bewahren.
                4. Gibt es keine relevanten Verstösse, gib eine leere Liste zurück.

                Regeldokumentation:
                ---------------
                {rules}
                ---------------

                Antworte in der Sprache des Eingabetextes."""


class AdvisorAgent(BaseAgent[RulesContainer, RulesValidationResult]):
    def __init__(self, config: Configuration):
        super().__init__(config, deps_type=RulesContainer, output_type=RulesValidationResult, enable_thinking=False)

    def create_agent(self, model: Model):
        agent = Agent(model=model, deps_type=RulesContainer, output_type=RulesValidationResult)

        @agent.instructions
        def get_instruction(ctx: RunContext[RulesContainer]):
            return INSTRUCTION.format(rules=ctx.deps.model_dump_json())

        return agent
