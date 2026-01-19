import time
from typing import final

from dcc_backend_common.logger import get_logger
from pydantic import BaseModel, Field
from returns.result import safe

from text_mate_backend.models.error_codes import REWRITE_TEXT_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.text_rewrite_models import RewriteResult
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent

logger = get_logger("text_rewrite_service")


class RewriteOutput(BaseModel):
    rewritten_text: str = Field(description="The rewritten text, in the same language as the input text.")


@final
class TextRewriteService:
    def __init__(self, llm_facade: PydanticAIAgent) -> None:
        logger.info("Initializing TextRewriteService")
        self.llm_facade = llm_facade

    @safe
    async def rewrite_text(self, text: str, context: str, options: str) -> RewriteResult:
        """Corrects a input text based on given options.

        Args:
            text: The text to be rewritten
            context: The surrounding context for the text
            options: Options to guide rewriting process

        Returns:
            ResultE containing either:
            - Success with RewriteResult containing alternative text options
            - Failure with an error message
        """
        text_length = len(text)
        text_preview = text[:50] + ("..." if text_length > 50 else "")

        logger.debug("Text preview", text_preview=text_preview)

        start_time = time.time()
        try:
            prompt = f"""
                    You are an expert in rewriting text. Take a given text and rewrite
                    it based on a provided context and options.
                    Your task:
                    1. Rewrite text based on a provided context and options.
                    2. Provide a list of all rewritten text options.
                    3. If no options are found, return an empty list.
                    4. The rewritten text should be in a same language as the input text.

                    Text to be rewritten:
                    ---------------
                    {text}
                    ---------------

                    Context:
                    ---------------
                    {context}
                    ---------------

                    Options:
                    {options}
                    """

            response = await self.llm_facade.run(
                prompt,
                RewriteOutput,
            )

            processing_time = time.time() - start_time

            # Replace special characters and <rewrite> tags
            out: str = response.rewritten_text.replace("ß", "ss")
            out = out.replace("<rewrite>", text)

            return RewriteResult(rewritten_text=out)

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Text rewrite failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=round(processing_time * 1000),
            )

            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": REWRITE_TEXT_ERROR,
                    "debugMessage": str(e),
                }
            ) from e
