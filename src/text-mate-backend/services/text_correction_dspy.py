# type: ignore

from typing import final

import dspy
from functional_monads.either import Either, right
from openai import OpenAI

from models.text_corretion_models import (
    CorrectionBlock,
    CorrectionResult,
    TextCorrectionOptions,
)
from utils.configuration import config


class SegmentInfo(dspy.Signature):
    """A segment is a singel word or a phrase that is corrected. It should as short as possible and only contain one error per segment."""

    original: str = dspy.OutputField(desc="The original segment")
    corrected: str = dspy.OutputField(desc="The corrected segment")
    explanation: str = dspy.OutputField(
        desc="A short explanation of the correction use the language of the original text"
    )


class ExtractInfo(dspy.Signature):
    """
    Correct the text.
    List all error in segments and return the list of segments with the original and corrected text and an explanation.
    Return an empty list if nothing to correct.
    """

    text: str = dspy.InputField(desc="The text to be corrected")
    segments: list[SegmentInfo] = dspy.OutputField(desc="a list of segments of the text")


@final
class TextCorrectionService:
    def __init__(self) -> None:
        lm = dspy.LM(
            model="hosted_vllm/Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4",
            api_base=config.openai_api_base_url,
            api_key="",
            max_tokens=1000,
            temperature=0.2,
        )
        dspy.configure(lm=lm)

        self.client = OpenAI(base_url=config.openai_api_base_url, api_key=config.openai_api_key)

    def correct_text(self, text: str, options: TextCorrectionOptions) -> Either[str, CorrectionResult]:
        """Corrects the input text based on given options.
        Returns Either[str, str] where:
        - Left(str) contains error message
        - Right(str) contains corrected text
        """

        module = dspy.Predict(ExtractInfo)
        response = module(text=text)
        print(dspy.inspect_history(n=3))

        return right(
            CorrectionResult(
                blocks=list(
                    map(
                        lambda segment: CorrectionBlock(
                            original=segment.original, corrected=[segment.corrected], explanation=segment.explanation
                        ),
                        response.segments,
                    )
                ),
                original=text,
            )
        )
