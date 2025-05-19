import json
from pathlib import Path
from typing import final

from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.ruel_models import Ruel, RuelDocumentDescription, RuelsContainer, RuelsValidationContainer
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_service")


@final
class AdvisorService:
    def __init__(self, llm_facade: LLMFacade) -> None:
        logger.info("Initializing AdvisorService")

        self.llm_facade = llm_facade
        self.ruel_container = RuelsContainer.model_validate_json(Path("docs/ruels.json").read_text())

    def get_docs(self) -> list[RuelDocumentDescription]:
        """
        Returns the documentation file names available for the advisor service.
        """
        json_data = json.loads(Path("docs/docs.json").read_text())
        doc_descriptions = [RuelDocumentDescription.model_validate(doc) for doc in json_data]

        doc_names = self.ruel_container.document_names

        return list(
            filter(
                lambda doc: doc.file in doc_names,
                doc_descriptions,
            )
        )

    def filter_ruels(self, docs: set[str]) -> list[Ruel]:
        return [rule for rule in self.ruel_container.rules if rule.file_name in docs]

    def check_text(self, text: str, docs: set[str]) -> RuelsValidationContainer:
        """
        Checks the text for any violations of the rules.
        """

        try:
            return self._check_text(text, docs)
        except Exception as e:
            logger.error(f"Error checking text: {e}")
            raise

    def _check_text(self, text: str, docs: set[str]) -> RuelsValidationContainer:
        rules = self.filter_ruels(docs)
        logger.info(f"Number of rules found: {len(rules)}")

        formatted_rules = self.format_ruels(rules)

        validated = self.llm_facade.structured_predict(
            RuelsValidationContainer,
            PromptTemplate(
                """You are an expert in editorial guidelines. Take the given document and extract all relevant rules.
                Your task:
                1. Check the text for any violations of the rules.
                2. Provide a list of all violations of the rules.
                3. Do not list ruels which are not violated.
                3. If no violations are found, return an empty list.

                Rules documentation:
                ---------------
                {rules}
                ---------------

                Input text:
                ---------------
                {text}
                ---------------

                Return your findings as structured data according to the specified format. Keep your answer in the original language.
                """,
                rules=formatted_rules,
                text=text,
            ),
        )

        return validated

    def format_ruels(self, ruels: list[Ruel]) -> str:
        """
        Formats the rules into a human-readable string.
        """
        return "\n".join([self.format_ruel(rule) for rule in ruels])

    def format_ruel(self, ruel: Ruel) -> str:
        """
        Formats the rule for better readability.
        """
        return f"""
        Rule Name: {ruel.name}
        Description: {ruel.description}
        File Name: {ruel.file_name}
        Page Number: {ruel.page_number}
        Example: {ruel.example}
        """
