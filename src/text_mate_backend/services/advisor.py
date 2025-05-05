import json
from pathlib import Path
from typing import Any, final

import dspy  # type: ignore
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.custom_vlmm import VllmCustom
from text_mate_backend.models.ruel_models import Ruel, RuelsContainer, RuelsValidationContainer
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_service")


@final
class AdvisorService:
    def __init__(self, config: Configuration) -> None:
        logger.info("Initializing AdvisorService")
        model_name = "hosted_vllm/ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g"
        logger.info(f"Using LLM model: {model_name}")

        self.ruel_container = RuelsContainer.model_validate_json(Path("docs/ruels.json").read_text())

        logger.info(f"Loaded {len(self.ruel_container.rules)} rules from docs/ruels.json")

        lm: Any = dspy.LM(
            model=model_name,
            api_base=config.openai_api_base_url,
            api_key=config.openai_api_key,
            max_tokens=1000,
            temperature=0.2,
        )
        dspy.configure(lm=lm)

        logger.info("AdvisorService initialized successfully")

    def get_docs(self) -> set[str]:
        """
        Returns the documentation for the advisor service.
        """

        return self.ruel_container.document_names

    def filter_ruels(self, docs: set[str]) -> list[Ruel]:
        return [rule for rule in self.ruel_container.rules if rule.file_name in docs]

    def check_text(self, text: str, docs: set[str]) -> RuelsValidationContainer:
        """
        Checks the text for any violations of the rules.
        """

        ruels = self.filter_ruels(docs)
        logger.info(f"Number of rules found: {len(ruels)}")

        llm = VllmCustom()
        sllm = llm.as_structured_llm(RuelsValidationContainer)

        validated: RuelsValidationContainer = sllm.structured_predict(
            RuelsValidationContainer,
            PromptTemplate(
                """You are an expert in editorial guidelines. Take the given document and extract all relevant ruels.
                Your task:
                1. Check the text for any violations of the rules.
                2. Provide a list of all violations of the rules.
                3. Write the ruels in the same language of the text.

                Rules documentation:
                {rules}

                Text to check:
                {text}

                Return your findings as structured data according to the specified format.
                """,
                rules=json.dumps([rule.model_dump() for rule in ruels]),
                text=text,
            ),
        )

        return validated
