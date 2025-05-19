import time
from typing import final

from llama_index.core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from returns.result import safe

from text_mate_backend.models.text_rewrite_models import RewriteResult, TextRewriteOptions
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("text_rewrite_service")


@final
class RewriteOutput(BaseModel):
    rewritten_text: str = Field(description="The rewritten text, in the same language as the input text.")


@final
class TextRewriteService:
    def __init__(self, llm_facade: LLMFacade) -> None:
        logger.info("Initializing TextRewriteService")
        self.llm_facade = llm_facade
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
            response = self.llm_facade.structured_predict(
                RewriteOutput,
                PromptTemplate(
                    """
                    You are an expert in rewriting text. Take the given text and rewrite it based on the provided context and options.
                    Your task:
                    1. Rewrite the text based on the provided context and options.
                    2. Provide a list of all rewritten text options.
                    3. If no options are found, return an empty list.
                    4. The rewritten text should be in the same language as the input text.

                    Text to be rewritten:
                    ---------------
                    {text}
                    ---------------

                    Context:
                    ---------------
                    {context}
                    ---------------

                    Options:
                    - Writing style: {writing_style}
                    - Target audience: {target_audience}
                    - Intend: {intend}
                    """,
                    text=text,
                    context=context,
                    writing_style=options.writing_style,
                    target_audience=options.target_audience,
                    intend=options.intend,
                ),
            )

            processing_time = time.time() - start_time
            option_count = len(response.rewritten_text)

            # Replace special characters and <rewrite> tags
            out: str = response.rewritten_text.replace("ß", "ss")
            out = out.replace("<rewrite>", text)

            logger.info(
                "Text rewrite completed successfully",
                processing_time_ms=round(processing_time * 1000),
                option_count=option_count,
            )

            return RewriteResult(rewritten_text=out)

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Text rewrite failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=round(processing_time * 1000),
            )
            raise
