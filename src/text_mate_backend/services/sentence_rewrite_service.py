from dcc_backend_common.logger import get_logger

from text_mate_backend.agents.agent_types.sentence_rewrite_agent import SentenceRewriteAgent
from text_mate_backend.models.sentence_rewrite_model import SentenceRewriteInput, SentenceRewriteResult
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("sentence_rewrite_service")


class SentenceRewriteService:
    """Service for rewriting sentences with alternative options."""

    def __init__(self, config: Configuration) -> None:
        self.agent = SentenceRewriteAgent(config)

    async def rewrite_sentence(self, sentence: str, context: str) -> SentenceRewriteResult:
        """
        Generate alternative rewrite options for a sentence based on context.

        Args:
            sentence: The sentence to rewrite
            context: The surrounding text context

        Returns:
            Result containing list of rewrite options or an exception
        """
        input_data = SentenceRewriteInput(sentence=sentence, context=context)
        result = await self.agent.run(deps=input_data)
        return result
