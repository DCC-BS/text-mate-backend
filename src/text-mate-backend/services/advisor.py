from typing import final

import dspy  # type: ignore
from functional_monads.either import Either, right
from pydantic import BaseModel

from models.text_rewrite_models import TextRewriteOptions
from utils.configuration import config


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
    def __init__(self) -> None:
        lm = dspy.LM(
            model="hosted_vllm/Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4",
            api_base=config.openai_api_base_url,
            api_key=config.openai_api_key,
            max_tokens=1000,
            temperature=0.2,
        )
        dspy.configure(lm=lm)

    def advise_changes(self, text: str, options: TextRewriteOptions) -> Either[str, AdvisorOutput]:
        """Corrects the input text based on given options."""

        module = dspy.Predict(AdvisorInfo)
        response = module(text=text, domain=options.domain, formality=options.formality)

        return right(
            AdvisorOutput(
                formalityScore=response.formalityScore,
                domainScore=response.domainScore,
                coherenceAndStructure=response.coherenceAndStructure,
                proposedChanges=response.proposedChanges,
            )
        )
