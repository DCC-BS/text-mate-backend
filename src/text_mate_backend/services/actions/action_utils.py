import time
from collections.abc import AsyncGenerator

from dcc_backend_common.logger import get_logger
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = get_logger("action_utils")


class PromptOptions(BaseModel):
    """
    A class to represent the options for a prompt.
    """

    system_prompt: str | None = None
    user_prompt: str
    llm_model: str


async def create_streaming_response(generator: AsyncGenerator[str, None]) -> StreamingResponse:
    logger = get_logger()

    async def generate() -> AsyncGenerator[str, None]:
        start_streaming_time = time.time()
        try:
            async for chunk in generator:
                yield chunk

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
