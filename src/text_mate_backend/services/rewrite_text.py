from typing import Callable, List, final

import dspy  # type: ignore
from returns.result import safe

from text_mate_backend.models.text_rewrite_models import RewriteResult, TextRewriteOptions
from text_mate_backend.services.dspy_facade import DspyFacade, DspyInitOptions
from text_mate_backend.utils.logger import get_logger

logger = get_logger()


class RewirteInfo(dspy.Signature):
    """
    Give alternatives to the text in respect of the domain and the formality.
    """

    text: str = dspy.InputField(desc="The text to be rewritten")
    context: str = dspy.InputField(desc="The full text of the document, text to be rewritten is marked with <rewrite>")
    writing_style: str = dspy.InputField(
        desc="""The writing style to use for the rewritten text.
                - general: General text
                - simple: Simple text
                - professional: Professional text
                - casual: Casual text
                - academic: Academic text
                - technical: Technical text""",
    )
    target_audience: str = dspy.InputField(
        desc="""The target audience to use for the rewritten text.
                - general: General audience
                - young: Young audience
                - adult: Adult audience
                - children: Children audience""",
    )
    intend: str = dspy.InputField(
        desc="""The intend to use for the rewritten text.
                - general: General text
                - persuasive: Persuasive text
                - informative: Informative text
                - descriptive: Descriptive text
                - narrative: Narrative text
                - entertaining: Entertaining text""",
    )
    options: List[str] = dspy.OutputField(desc="A list of alternative texts")


@final
class TextRewriteService:
    def __init__(self, dspy_facade_factory: Callable[..., DspyFacade]) -> None:
        self.dspy_facade: DspyFacade = dspy_facade_factory(
            options=DspyInitOptions(
                temperature=0.6,
                max_tokens=1000,
            )
        )

    @safe
    def rewrite_text(self, text: str, context: str, options: TextRewriteOptions) -> RewriteResult:
        """Corrects the input text based on given options.

        Args:
            text: The text to be rewritten
            context: The surrounding context for the text
            options: Options to guide the rewriting process

        Returns:
            ResultE containing either:
            - Success with RewriteResult containing alternative text options
            - Failure with an error message
        """

        response: RewirteInfo = self.dspy_facade.predict(
            RewirteInfo,
            text=text,
            context=context,
            writing_style=options.writing_style,
            target_audience=options.target_audience,
            intend=options.intend,
        )

        out_options: List[str] = response.options
        out_options = list(map(lambda option: option.replace("<rewrite>", text).replace("ß", "ss"), out_options))

        return RewriteResult(options=out_options)
