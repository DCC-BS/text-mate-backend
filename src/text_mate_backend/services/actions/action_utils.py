import time
from typing import Generator, Iterator

from fastapi.responses import StreamingResponse
from openai import BaseModel, OpenAI
from openai.types.chat import ChatCompletionChunk

from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger("action_utils")
config = Configuration()

SYSTEM_PROMPT_POSTFIX: str = (
    "Format the text as plain text, don't use any html tags or markdwon."
    "Answer in the same language as the input text."
    "Only respond with the answer, do not add any other text."
)

# SYSTEM_PROMPT_POSTFIX = (
#     "Format the text as html, using <p> tags for paragraphs and <br> tags for line breaks."
#     "Use <strong> for bold text."
#     "Use <ul> and <li> for lists."
#     "Do not use any other tags."
#     "Answer in the same language as the input text."
#     "Only respond with the html code, do not add any other text."
# )


class PrompOptions(BaseModel):
    """
    A class to represent the options for a prompt.
    """

    system_prompt: str
    user_prompt: str
    temperature: float = 0.7


def run_prompt(options: PrompOptions, llm: OpenAI) -> StreamingResponse:
    """
    Runs the given prompt using the OpenAI API and returns a streaming response.

    Args:
        options: The prompt options including system prompt, user prompt and temperature
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse that yields the generated text chunks
    """
    # Get request details for logging
    user_prompt_preview = options.user_prompt[:100] + ("..." if len(options.user_prompt) > 100 else "")

    logger.info("Starting OpenAI streaming request", model=config.llm_model, temperature=options.temperature)
    logger.debug("Prompt details", user_prompt=user_prompt_preview, system_prompt=options.system_prompt)

    start_time = time.time()
    try:
        stream: Iterator[ChatCompletionChunk] = llm.chat.completions.create(
            model=config.llm_model,
            messages=[
                {"role": "system", "content": f"{options.system_prompt} {SYSTEM_PROMPT_POSTFIX}"},
                {"role": "user", "content": options.user_prompt},
            ],
            stream=True,
            temperature=options.temperature,
        )

        def generate() -> Generator[str, None, None]:
            total_tokens = 0
            start_streaming_time = time.time()
            try:
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content.replace("ß", "ss")
                        total_tokens += 1
                        yield content

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
