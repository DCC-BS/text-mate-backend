import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast, final

from fastapi_azure_auth.user import User
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.models.error_codes import TextMateApiErrorCodes
from backend_common.fastapi_error_handling import ApiErrorException
from text_mate_backend.models.rule_models import (
    RuelDocumentDescription,
    RuelValidation,
    Rule,
    RulesContainer,
    RulesValidationContainer,
)
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_service")
MAX_RULES_PER_REQUEST = 3
MAX_RULES = 20


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
        json_data = cast(list[dict[str, object]], json.loads(Path("docs/docs.json").read_text()))
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
        Checks the text for any violations of the rules and returns an aggregated result.
        """

        try:
            return self._check_text(text, docs)
        except Exception as e:
            logger.error(f"Error checking text: {e}")
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": TextMateApiErrorCodes.CHECK_TEXT_ERROR,
                    "debugMessage": str(e),
                }
            ) from e

    def check_text_stream(self, text: str, docs: set[str]) -> Iterator[RulesValidationContainer]:
        """
        Checks the text for any violations of the rules and yields validation results
        batch-by-batch. This is intended for streaming (SSE) responses.
        """

        try:
            yield from self._check_text_stream(text, docs)
        except Exception as e:
            logger.error(f"Error checking text (stream): {e}")
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": TextMateApiErrorCodes.CHECK_TEXT_ERROR,
                    "debugMessage": str(e),
                }
            ) from e

    def _check_text(self, text: str, docs: set[str]) -> RulesValidationContainer:
        rules = self.filter_rules(docs)

        if not rules:
            return RulesValidationContainer(rules=[])

        aggregated_rules: list[RuelValidation] = []

        for rule_batch in self._batched_rules(rules, MAX_RULES_PER_REQUEST):
            formatted_rules = self.format_rules(rule_batch)
            validation_result = self._run_rule_validation(formatted_rules, text)
            aggregated_rules.extend(validation_result.rules or [])

        return RulesValidationContainer(rules=aggregated_rules)

    def _check_text_stream(self, text: str, docs: set[str]) -> Iterator[RulesValidationContainer]:
        rules = self.filter_rules(docs)

        if not rules:
            # Maintain parity with the non-streaming API by yielding a single empty container
            yield RulesValidationContainer(rules=[])
            return

        for rule_batch in self._batched_rules(rules, MAX_RULES_PER_REQUEST):
            formatted_rules = self.format_rules(rule_batch)
            validation_result = self._run_rule_validation(formatted_rules, text)
            yield validation_result

    def _run_rule_validation(self, formatted_rules: str, text: str) -> RulesValidationContainer:
        """
        Validate the input text against the provided, formatted editorial rules using the configured LLM.

        Parameters:
            formatted_rules (str): Human-readable rules text to be applied during validation (already formatted).
            text (str): The input text to check for rule violations.

        Returns:
            RulesValidationContainer: Container with detected rule violations; contains an empty list when no qualifying violations are found.
        """
        return self.llm_facade.structured_predict(
            response_type=RulesValidationContainer,
            prompt=PromptTemplate(
                """You are an expert in editorial guidelines. Review only the given rules and
                identify any clear, material violations in the input text.
                Guidelines:
                1. Focus on substantive issues that meaningfully impact clarity, accuracy, tone, wrong use of words, abbreviations, etc.
                2. If you are unsure whether a rule is violated, do not report it.
                3. Provide practical, respectful rewrite proposals that keep the author's intent.
                4. If no qualifying violations exist, return an empty list.

                Follow this schema for the response:
                {schema}


                Rules documentation:
                ---------------
                {rules}
                ---------------

                Input text:
                ---------------
                {text}
                ---------------

                Keep your answer in the original language.
                """,  # noqa: E501
                schema=str(RulesValidationContainer.model_json_schema()),
                rules=formatted_rules,
                text=text,
            ),
        )

    def _batched_rules(self, rules: list[Rule], batch_size: int, max_rules: int = MAX_RULES) -> Iterator[list[Rule]]:
        for i in range(0, min(len(rules), max_rules), batch_size):
            yield rules[i : i + batch_size]

    def format_rules(self, rules: list[Rule]) -> str:
        return "\n".join([self.format_rule(rule) for rule in rules])

    def format_rule(self, rule: Rule) -> str:
        return f"""
        Rule Name: {rule.name}
        Description: {rule.description}
        File Name: {rule.file_name}
        Page Number: {rule.page_number}
        Example: {rule.example}
        """
