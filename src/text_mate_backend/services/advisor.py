import json
from pathlib import Path
from typing import final

from fastapi_azure_auth.user import User
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.ruel_models import RuelDocumentDescription, Rule, RulesContainer, RulesValidationContainer
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_service")


def has_access(user: User, doc: RuelDocumentDescription) -> bool:
    if "all" in doc.access:
        return True

    for roles in user.roles:
        for access in doc.access:
            if roles == access:
                return True

    return False


@final
class AdvisorService:
    def __init__(self, llm_facade: LLMFacade) -> None:
        logger.info("Initializing AdvisorService")

        self.llm_facade = llm_facade
        self.ruel_container = RulesContainer.model_validate_json(Path("docs/rules.json").read_text())

    def get_docs(self, user: User) -> list[RuelDocumentDescription]:
        """
        Returns the documentation file names available for the advisor service.
        """
        json_data: list[object] = json.loads(Path("docs/docs.json").read_text())
        doc_descriptions: list[RuelDocumentDescription] = [
            RuelDocumentDescription.model_validate(doc) for doc in json_data
        ]

        doc_descriptions = list(filter(lambda doc: has_access(user, doc), doc_descriptions))

        doc_names = self.ruel_container.document_names

        return list(
            filter(
                lambda doc: doc.file in doc_names,
                doc_descriptions,
            )
        )

    def filter_rules(self, docs: set[str]) -> list[Rule]:
        return [rule for rule in self.ruel_container.rules if rule.file_name in docs]

    def check_text(self, text: str, docs: set[str]) -> RulesValidationContainer:
        """
        Checks the text for any violations of the rules.
        """

        try:
            return self._check_text(text, docs)
        except Exception as e:
            logger.error(f"Error checking text: {e}")
            raise

    def _check_text(self, text: str, docs: set[str]) -> RulesValidationContainer:
        rules = self.filter_rules(docs)

        formatted_rules = self.format_rules(rules)

        validated = self.llm_facade.structured_predict(
            RulesValidationContainer,
            PromptTemplate(
                """You are an expert in editorial guidelines. Take the given rules and
                extract all violated rules in the input text.
                Your task:
                1. Check the text for any violations of the rules.
                2. Provide a list of all violated rules in the specified format.
                3. Do not list rules which are not violated.
                4. If no violations are found, return an empty list.

                Rules documentation:
                ---------------
                {rules}
                ---------------

                Input text:
                ---------------
                {text}
                ---------------

                Return your findings as structured data according to the specified format.
                Keep your answer in the original language.
                """,
                rules=formatted_rules,
                text=text,
            ),
        )

        return validated

    def format_rules(self, rules: list[Rule]) -> str:
        """
        Formats the rules into a human-readable string.
        """
        return "\n".join([self.format_rule(rule) for rule in rules])

    def format_rule(self, rule: Rule) -> str:
        """
        Formats the rule for better readability.
        """
        return f"""
        Rule Name: {rule.name}
        Description: {rule.description}
        File Name: {rule.file_name}
        Page Number: {rule.page_number}
        Example: {rule.example}
        """
