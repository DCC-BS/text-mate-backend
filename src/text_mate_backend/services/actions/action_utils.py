import time
from collections.abc import Generator, Iterator

from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate
from pydantic import BaseModel

from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("action_utils")


class PromptOptions(BaseModel):
    """
    A class to represent the options for a prompt.
    """

    prompt: str
    llm_model: str


def run_prompt(options: PromptOptions, llm_facade: LLMFacade) -> StreamingResponse:
    """
    Runs the given prompt using the OpenAI API and returns a streaming response.

    Args:
        options: The prompt options including system prompt, user prompt and temperature
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse that yields the generated text chunks
    """
    # Get request details for logging
    logger.info("Starting OpenAI streaming request", model=options.llm_model)

    start_time = time.time()
    try:
        prompt = PromptTemplate(
            """
                {prompt}

                - Format the text as plain text, don't use any html tags or markdown.
                - Answer in the same language as the input text.
                - Only respond with the answer, do not add any other text.
                - Don't add any extra information or context.
                - Don't add any whitespaces.
               """,
            prompt=options.prompt,
        ).format()

        stream: Iterator[str] = llm_facade.stream_complete(prompt)

        def generate() -> Generator[str, None, None]:
            total_tokens = 0
            start_streaming_time = time.time()
            try:
                isPrefixWhiteSpace = True

                for chunk in stream:
                    if isPrefixWhiteSpace and chunk == " " or chunk == "\n" or chunk == "\n\n":
                        continue

                    isPrefixWhiteSpace = False
                    yield chunk

                # Log streaming completion
                streaming_duration = time.time() - start_streaming_time
                logger.info(
                    "Streaming completed",
                    tokens_streamed=total_tokens,
                    streaming_duration_ms=round(streaming_duration * 1000),
                )
            except Exception as e:
                # Log errors during streaming
                streaming_duration = time.time() - start_streaming_time
                logger.error(
                    "Error during streaming",
                    error=str(e),
                    error_type=type(e).__name__,
                    tokens_streamed=total_tokens,
                    streaming_duration_ms=round(streaming_duration * 1000),
                )
                raise

        logger.info("OpenAI API call initiated successfully")
        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        setup_time = time.time() - start_time
        logger.error(
            "Failed to initiate OpenAI streaming request",
            error=str(e),
            error_type=type(e).__name__,
            setup_time_ms=round(setup_time * 1000),
        )
        raise
