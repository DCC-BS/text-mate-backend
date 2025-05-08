import json
from pathlib import Path
from typing import Any, final

import dspy  # type: ignore
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.custom_vlmm import VllmCustom
from text_mate_backend.models.ruel_models import Ruel, RuelDocumentDescription, RuelsContainer, RuelsValidationContainer
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_service")


@final
class AdvisorService:
    def __init__(self, config: Configuration) -> None:
        logger.info("Initializing AdvisorService")

        self.llm = VllmCustom()
        self.ruel_container = RuelsContainer.model_validate_json(Path("docs/ruels.json").read_text())

    def get_docs(self) -> list[RuelDocumentDescription]:
        """
        Returns the documentation file names available for the advisor service.
        """
        json_data = json.loads(Path("docs/docs.json").read_text())
        doc_descriptions = [RuelDocumentDescription.model_validate(doc) for doc in json_data]

        doc_names = self.ruel_container.document_names

        return filter(
            lambda doc: doc.file in doc_names,
            doc_descriptions,
        )

    def filter_ruels(self, docs: set[str]) -> list[Ruel]:
        return [rule for rule in self.ruel_container.rules if rule.file_name in docs]

    def check_text(self, text: str, docs: set[str]) -> RuelsValidationContainer:
        """
        Checks the text for any violations of the rules.
        """

        rules = self.filter_ruels(docs)
        logger.info(f"Number of rules found: {len(rules)}")

        sllm = self.llm.as_structured_llm(RuelsValidationContainer)

        validated: RuelsValidationContainer = sllm.structured_predict(
            RuelsValidationContainer,
            PromptTemplate(
                """You are an expert in editorial guidelines. Take the given document and extract all relevant rules.
                Your task:
                1. Check the text for any violations of the rules.
                2. Provide a list of all violations of the rules.
                3. If no violations are found, return an empty list.

                Rules documentation:
                {rules}

                input text:
                {text}

                Return your findings as structured data according to the specified format. Keep your answer in the original language.
                """,
                rules=json.dumps([rule.model_dump() for rule in rules]),
                text=text,
            ),
        )

        return validated
