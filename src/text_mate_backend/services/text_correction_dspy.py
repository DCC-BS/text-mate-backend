# type: ignore

from typing import Any, final

import dspy
from openai import OpenAI
from returns.result import ResultE, safe

from text_mate_backend.models.text_corretion_models import (
    CorrectionBlock,
    CorrectionResult,
    TextCorrectionOptions,
)
from text_mate_backend.utils.configuration import Configuration


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
        config: Configuration = Configuration()
        lm: Any = dspy.LM(
            model="hosted_vllm/Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4",
            api_base=config.openai_api_base_url,
            api_key="",
            max_tokens=1000,
            temperature=0.2,
        )
        dspy.configure(lm=lm)

        self.client: OpenAI = OpenAI(base_url=config.openai_api_base_url, api_key=config.openai_api_key)

    @safe
    def correct_text(self, text: str, options: TextCorrectionOptions) -> ResultE[CorrectionResult]:
        """
        Corrects the input text based on given options.

        Args:
            text: The input text to be corrected
            options: Configuration options for text correction

        Returns:
            ResultE containing either:
            - Success with CorrectionResult containing the corrected text blocks
            - Failure with an error message
        """

        module: Any = dspy.Predict(ExtractInfo)
        response: ExtractInfo = module(text=text)
        print(dspy.inspect_history(n=3))

        return CorrectionResult(
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
