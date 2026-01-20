"""Plain language agent for converting text to simple language."""

from pydantic_ai import RunContext

from text_mate_backend.agents.base import BaseAgent
from text_mate_backend.utils.configuration import Configuration


class PlainLanguageAgent(BaseAgent):
    """Agent for converting text to plain language (Leichte Sprache)."""

    def __init__(
        self,
        config: Configuration,
        language_level: str = "A2-A1",
        **kwargs,
    ):
        self.language_level = language_level
        super().__init__(config, **kwargs)

    def get_name(self) -> str:
        return "PlainLanguage"

    def get_system_prompt(self) -> str:
        return f"""
        You are a writing assistant specialized in converting text to plain language.
        Your task is to rewrite the given text in a simple, easy-to-understand way.
        The target language level is: {self.language_level}.
        
        Guidelines:
        - Use short sentences with simple structure
        - Avoid complex words and phrases
        - Use active voice instead of passive voice
        - Explain difficult concepts if necessary
        - The rewritten text should be in the same language as the input text
        - Format as markdown, don't use HTML tags
        - Don't include introductory or closing remarks
        - Only respond with the rewritten text
        """

    def _register_tools(self, agent):
        """Register plain language specific tools."""

        @agent.tool
        async def check_readability_score(ctx: RunContext, text: str) -> dict:
            """Calculate basic readability metrics."""
            words = text.split()
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            avg_word_length = sum(len(w) for w in words) / max(len(words), 1)
            avg_sentence_length = len(words) / max(len(sentences), 1)

            return {
                "word_count": len(words),
                "sentence_count": len(sentences),
                "avg_word_length": round(avg_word_length, 2),
                "avg_sentence_length": round(avg_sentence_length, 2),
            }

        return agent
