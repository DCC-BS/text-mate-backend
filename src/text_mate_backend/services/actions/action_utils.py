import re
import time
from collections.abc import AsyncGenerator

from dcc_backend_common.logger import get_logger
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent

logger = get_logger("action_utils")


class PromptOptions(BaseModel):
    """
    A class to represent the options for a prompt.
    """

    system_prompt: str | None = None
    user_prompt: str
    llm_model: str


async def run_prompt(options: PromptOptions, llm_facade: PydanticAIAgent) -> StreamingResponse:
    """
    Runs a given prompt using the OpenAI API and returns a streaming response.

    Args:
        options: The prompt options including system prompt, user prompt and temperature
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse that yields generated text chunks
    """

    start_time = time.time()
    try:
        prompt = f"""
        {options.system_prompt}

        - Format the text as markdown, don't use any html tags.
        - Don't include any introductory or closing remarks.
        - Answer in the same language as the input text.
        - Only respond with the answer, do not add any other text.
        - Don't add any extra information or context.
        - Don't add any whitespaces.

        {options.user_prompt}
        """

        async def generate() -> AsyncGenerator[str, None]:
            start_streaming_time = time.time()
            try:
                isPrefixWhiteSpace = True

                async for chunk in llm_facade.stream_text(prompt):
                    if isPrefixWhiteSpace and (re.match(r"^\s*$", chunk)):
                        continue

                    isPrefixWhiteSpace = False
                    yield chunk

                # Log streaming completion
                streaming_duration = time.time() - start_streaming_time
            except Exception as e:
                # Log errors during streaming
                streaming_duration = time.time() - start_streaming_time
                logger.exception(
                    "Error during streaming",
                    error=str(e),
                    error_type=type(e).__name__,
                    streaming_duration_ms=round(streaming_duration * 1000),
                )
                raise

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        setup_time = time.time() - start_time
        logger.exception(
            "Failed to initiate OpenAI streaming request",
            error=str(e),
            error_type=type(e).__name__,
            setup_time_ms=round(setup_time * 1000),
        )
        raise
