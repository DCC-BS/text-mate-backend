from collections.abc import AsyncGenerator
from typing import final

from dcc_backend_common.logger import get_logger

from text_mate_backend.agents.agent_types.fix_agent import FixAgent
from text_mate_backend.models.error_codes import FIX_TEXT_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.fix_models import FixRequest, FixThread
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("fix_service")

AGENT_TIMEOUT_SECONDS = 120


@final
class FixService:
    def __init__(self, config: Configuration) -> None:
        logger.info("Initializing FixService")
        self.config = config
        self.agent = FixAgent(config)

    async def fix_text_stream(self, text: str, threads: list[FixThread]) -> AsyncGenerator[str, None]:
        """
        Stream the corrected text as plain text deltas.

        Produces a complete new text with all thread proposals applied, using
        reason/notes as LLM context. Completion is signalled by closing the stream.
        """
        request = FixRequest(text=text, threads=threads)

        try:
            async for chunk in self.agent.run_stream_text(user_prompt=text, deps=request):
                yield chunk
        except Exception as e:
            logger.error(f"Error fixing text (stream): {e}")
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": FIX_TEXT_ERROR,
                    "debugMessage": str(e),
                }
            ) from e
