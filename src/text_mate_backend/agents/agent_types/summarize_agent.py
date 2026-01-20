"""Summarize agent for text summarization."""

from pydantic_ai import RunContext

from text_mate_backend.agents.base import BaseAgent
from text_mate_backend.models.output_models import SummaryOutput
from text_mate_backend.utils.configuration import Configuration


class SummarizeAgent(BaseAgent):
    """Agent for text summarization."""

    def __init__(
        self,
        config: Configuration,
        summary_type: str = "concise",
        **kwargs,
    ):
        self.summary_type = summary_type
        super().__init__(config, output_type=SummaryOutput, **kwargs)

    def get_name(self) -> str:
        return "Summarize"

    def get_system_prompt(self) -> str:
        type_instructions = {
            'sentence': 'The summary should be exactly one sentence long.',
            'three_sentence': 'The summary should be exactly three sentences long.',
            'paragraph': 'The summary should be one paragraph long.',
            'page': 'The summary should be up to one page long.',
            'management': 'The summary should be a management summary - focus on key points for decision-makers, one paragraph to one page long.',
            'concise': 'Keep it brief and to the point.',
            'detailed': 'Include important details and nuances.',
        }.get(self.summary_type, 'Provide a clear summary.')

        return f"""
        You are an expert summarizer. Extract key points and central message.
        The summary should be in the same language as the input text.
        
        {type_instructions}
        
        Format the response as JSON with the following structure:
        - summary: The summarized text
        - key_points: A list of key points extracted from the text
        - original_length: The number of characters in the original text
        - summary_length: The number of characters in the summary
        """

    def _register_tools(self, agent):
        """Register summarization tools."""

        @agent.tool
        async def calculate_readability(ctx: RunContext, text: str) -> dict:
            """Calculate readability metrics."""
            words = text.split()
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            avg_word_length = sum(len(w) for w in words) / max(len(words), 1)

            return {
                "word_count": len(words),
                "sentence_count": len(sentences),
                "avg_word_length": round(avg_word_length, 2),
            }

        @agent.tool
        async def extract_keywords(ctx: RunContext, text: str, max_count: int = 5) -> list[str]:
            """Extract main keywords from text (simple implementation)."""
            from collections import Counter
            import re

            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
            word_freq = Counter(words)
            return [word for word, _ in word_freq.most_common(max_count)]

        return agent
