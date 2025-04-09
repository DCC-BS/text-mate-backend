import time
from typing import Callable, List, final

import dspy  # type: ignore
from returns.result import safe

from text_mate_backend.models.text_rewrite_models import RewriteResult, TextRewriteOptions
from text_mate_backend.services.dspy_facade import DspyFacade, DspyInitOptions
from text_mate_backend.utils.logger import get_logger

logger = get_logger("text_rewrite_service")


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
        logger.info("Initializing TextRewriteService")
        self.dspy_facade: DspyFacade = dspy_facade_factory(
            options=DspyInitOptions(
                temperature=0.6,
                max_tokens=1000,
            )
        )
        logger.info("TextRewriteService initialized successfully")

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
        text_length = len(text)
        context_length = len(context)
        text_preview = text[:50] + ("..." if text_length > 50 else "")

        logger.info(
            "Processing text rewrite request",
            text_length=text_length,
            context_length=context_length,
            writing_style=options.writing_style,
            target_audience=options.target_audience,
            intend=options.intend,
        )
        logger.debug("Text preview", text_preview=text_preview)

        start_time = time.time()
        try:
            response: RewirteInfo = self.dspy_facade.predict(
                RewirteInfo,
                text=text,
                context=context,
                writing_style=options.writing_style,
                target_audience=options.target_audience,
                intend=options.intend,
            )

            processing_time = time.time() - start_time
            option_count = len(response.options)

            out_options: List[str] = response.options
            out_options = list(map(lambda option: option.replace("<rewrite>", text).replace("ß", "ss"), out_options))

            logger.info(
                "Text rewrite completed successfully",
                processing_time_ms=round(processing_time * 1000),
                option_count=option_count,
            )

            for i, option in enumerate(out_options):
                logger.debug(
                    f"Rewrite option {i + 1}", option_preview=option[:50] + ("..." if len(option) > 50 else "")
                )

            return RewriteResult(options=out_options)

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Text rewrite failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=round(processing_time * 1000),
            )
            raise
