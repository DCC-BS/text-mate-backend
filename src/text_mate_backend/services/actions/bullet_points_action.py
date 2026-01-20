from typing import AsyncGenerator
from fastapi.responses import StreamingResponse

from pydantic_ai.ui._web.app import AgentDepsT
from text_mate_backend.agents.agent_types.bullet_point_agent import get_bulletpoint_agent
from text_mate_backend.agents.run_agent import run_stream_text
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration
import time

from dcc_backend_common.logger import get_logger


async def bullet_points(
    context: QuickActionContext, config: Configuration, llm_facade: PydanticAIAgent
) -> StreamingResponse:
    """
    Converts a given text into a structured bullet point format with key points.

    Args:
        context: QuickActionContext containing input text and bullet points option
        config: Configuration containing LLM model and other settings
        llm_facade: The PydanticAIAgent instance to use for generating the response

    Returns:
        A StreamingResponse containing bullet points version of text
    """
    logger = get_logger()

    agent = get_bulletpoint_agent(config)

    start_time = time.time()
    try:

        async def generate() -> AsyncGenerator[str, None]:
            start_streaming_time = time.time()
            try:
                isPrefixWhiteSpace = True

                async with agent.run_stream(user_prompt=context.text) as result:
                    async for chunk in run_stream_text(result):
                        yield chunk

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
