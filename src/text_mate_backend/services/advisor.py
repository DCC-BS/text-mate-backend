import time
from typing import Any, final

import dspy  # type: ignore
from pydantic import BaseModel
from returns.result import safe

from text_mate_backend.models.text_rewrite_models import TextRewriteOptions
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_service")


class ProposeChanges(dspy.Signature):
    """
    Propose changes to the text.
    """

    newText: str = dspy.OutputField(desc="The corrected text")
    description: str = dspy.OutputField(desc="A description of the changes made to the text")


class AdvisorInfo(dspy.Signature):
    """
    You are an assistant that helps improve the formality, domain, and coherence of text.
    Give advice on how to improve the text.
    Focus on the formality, domain, and coherence of the text and not on grammar or spelling mistakes.
    If the text is in german use ss instead of ß.
    """

    text: str = dspy.InputField(desc="The text to inspect")
    formality: str = dspy.InputField(desc="The formality to use for the rewritten text")
    domain: str = dspy.InputField(desc="The domain the use for the rewritten text")

    formalityScore: float = dspy.OutputField(
        desc="Assess how well the text matches the desired formality level. The formality score of the text normalized to a scale of 0 to 1"
    )
    domainScore: float = dspy.OutputField(
        desc="Evaluate how well the text fits the specified domain. The domain score of the text normalized to a scale of 0 to 1"
    )

    coherenceAndStructure: float = dspy.OutputField(
        desc="Analyze the logical flow and consistency of ideas in the text. The coherence and structure score of the text normalized to a scale of 0 to 1"
    )

    proposedChanges: str = dspy.OutputField(
        desc="Report in the language of the original text about the proposed changes to the text formatted pretty in markdwon."
    )


class AdvisorOutput(BaseModel):
    formalityScore: float
    domainScore: float
    coherenceAndStructure: float
    proposedChanges: str


@final
class AdvisorService:
    def __init__(self, config: Configuration) -> None:
        logger.info("Initializing AdvisorService")
        model_name = "hosted_vllm/Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4"
        logger.info(f"Using LLM model: {model_name}")

        lm: Any = dspy.LM(
            model=model_name,
            api_base=config.openai_api_base_url,
            api_key=config.openai_api_key,
            max_tokens=1000,
            temperature=0.2,
        )
        dspy.configure(lm=lm)
        logger.info("AdvisorService initialized successfully")

    @safe
    def advise_changes(self, text: str, options: TextRewriteOptions) -> AdvisorOutput:
        """
        Analyzes the text and provides advice for improvements.

        Args:
            text: The input text to analyze
            options: Configuration options for text analysis

        Returns:
            AdvisorOutput containing scores and proposed changes
        """
        text_length = len(text)
        text_preview = text[:50] + ("..." if text_length > 50 else "")

        logger.info(f"Processing advisor request", text_length=text_length)
        logger.debug("Text preview", preview=text_preview)

        start_time = time.time()
        try:
            module: Any = dspy.Predict(AdvisorInfo)

            # Make API call to analyze text
            logger.debug("Calling LLM for text analysis")
            response: AdvisorInfo = module(text=text, domain="", formality="")

            processing_time = time.time() - start_time

            result = AdvisorOutput(
                formalityScore=response.formalityScore,
                domainScore=response.domainScore,
                coherenceAndStructure=response.coherenceAndStructure,
                proposedChanges=response.proposedChanges,
            )

            logger.info(
                "Advisor analysis completed successfully",
                processing_time_ms=round(processing_time * 1000),
                formality_score=result.formalityScore,
                domain_score=result.domainScore,
                coherence_score=result.coherenceAndStructure,
            )

            changes_preview = result.proposedChanges[:50] + ("..." if len(result.proposedChanges) > 50 else "")
            logger.debug("Proposed changes preview", preview=changes_preview)

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Advisor analysis failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=round(processing_time * 1000),
            )
            raise
