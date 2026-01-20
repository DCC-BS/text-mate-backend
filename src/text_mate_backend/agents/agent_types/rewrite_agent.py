"""Rewrite agent for text editing operations."""

from typing import Literal
from pydantic_ai import RunContext

from text_mate_backend.agents.base import BaseAgent
from text_mate_backend.utils.configuration import Configuration


class RewriteAgent(BaseAgent):
    """Agent for text rewriting and editing operations."""

    def __init__(
        self,
        config: Configuration,
        operation: Literal['rewrite', 'simplify', 'formality', 'medium'] = 'rewrite',
        tone: Literal['formal', 'casual', 'neutral'] = 'neutral',
        **kwargs,
    ):
        self.operation = operation
        self.tone = tone
        super().__init__(config, **kwargs)

    def get_name(self) -> str:
        return "Rewrite"

    def get_system_prompt(self) -> str:
        operation_instructions = {
            'rewrite': 'Rewrite the text based on the provided options.',
            'simplify': 'Simplify the text by removing complex words and phrases.',
            'formality': f'Change the formality level to {self.tone}.',
            'medium': 'Improve the text for medium-length communication.',
        }.get(self.operation, 'Rewrite the text.')

        return f"""
        You are an expert text editor specializing in {self.operation}.
        
        {operation_instructions}
        
        Guidelines:
        - Maintain the original meaning while improving clarity
        - The rewritten text should be in the same language as input text
        - Format as markdown, don't use HTML tags
        - Don't include any introductory or closing remarks
        - Only respond with the rewritten text
        - Don't add any extra information or context
        """

    def _register_tools(self, agent):
        """Register text editing tools."""

        @agent.tool
        async def count_words(ctx: RunContext, text: str) -> int:
            """Count words in the given text."""
            return len(text.split())

        @agent.tool
        async def count_characters(ctx: RunContext, text: str, include_spaces: bool = True) -> int:
            """Count characters in the given text."""
            return len(text) if include_spaces else len(text.replace(' ', ''))

        @agent.tool
        async def count_sentences(ctx: RunContext, text: str) -> int:
            """Count sentences in the given text."""
            import re
            return len([s for s in re.split(r'[.!?]+', text) if s.strip()])

        return agent
