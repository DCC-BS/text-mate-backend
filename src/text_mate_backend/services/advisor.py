import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast, final

from dcc_backend_common.logger import get_logger
from fastapi_azure_auth.user import User
from typing_extensions import AsyncIterator

from text_mate_backend.agents.agent_types.advisor_agent import AdvisorAgent
from text_mate_backend.models.error_codes import CHECK_TEXT_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.rule_models import (
    RuelDocumentDescription,
    Rule,
    RulesContainer,
    RulesValidationContainer,
)
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("advisor_service")
MAX_RULES_PER_REQUEST = 3
MAX_RULES = 20


@final
class AdvisorService:
    def __init__(self, config: Configuration) -> None:
        logger.info("Initializing AdvisorService")

        self.config = config
        self.ruel_container = RulesContainer.model_validate_json(Path("docs/rules.json").read_text())
        self.agent = AdvisorAgent(config)

    def get_docs(self, user: User | None) -> list[RuelDocumentDescription]:
        """
        Returns the documentation file names available for the advisor service.
        """
        json_data = cast(list[dict[str, object]], json.loads(Path("docs/docs.json").read_text()))
        doc_descriptions: list[RuelDocumentDescription] = [
            RuelDocumentDescription.model_validate(doc) for doc in json_data
        ]

        doc_descriptions = list(filter(lambda doc: self._has_access(user, doc), doc_descriptions))

        doc_names = self.ruel_container.document_names

        return list(
            filter(
                lambda doc: doc.file in doc_names,
                doc_descriptions,
            )
        )

    def filter_rules(self, docs: set[str]) -> list[Rule]:
        return [rule for rule in self.ruel_container.rules if rule.file_name in docs]

    async def check_text_stream(self, text: str, docs: set[str]) -> AsyncIterator[RulesValidationContainer]:
        """
        Checks the text for any violations of the rules and yields validation results
        batch-by-batch. This is intended for streaming (SSE) responses.
        """

        try:
            async for result in self._check_text_stream(text, docs):
                yield result
        except Exception as e:
            logger.error(f"Error checking text (stream): {e}")
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": CHECK_TEXT_ERROR,
                    "debugMessage": str(e),
                }
            ) from e

    def _has_access(self, user: User | None, doc: RuelDocumentDescription) -> bool:
        if "all" in doc.access:
            return True

        if user is None:
            if self.config.disable_auth:
                return True
            else:
                raise ValueError("User is none when authentification is expected")

        for roles in user.roles:
            for access in doc.access:
                if roles == access:
                    return True

        return False

    async def _check_text_stream(self, text: str, docs: set[str]) -> AsyncIterator[RulesValidationContainer]:
        rules = self.filter_rules(docs)

        if not rules:
            logger.warn(f"No rules found for the documents {docs}")
            # Maintain parity with the non-streaming API by yielding a single empty container
            yield RulesValidationContainer(rules=[])
            return

        for rule_batch in self._batched_rules(rules, MAX_RULES_PER_REQUEST):
            validation_result = await self.agent.run(text, deps=RulesContainer(rules=rule_batch))
            yield validation_result

    def _batched_rules(self, rules: list[Rule], batch_size: int, max_rules: int = MAX_RULES) -> Iterator[list[Rule]]:
        for i in range(0, min(len(rules), max_rules), batch_size):
            yield rules[i : i + batch_size]
