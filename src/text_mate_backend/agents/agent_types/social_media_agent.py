"""Social media agent for social media content creation."""

from pydantic_ai import RunContext

from text_mate_backend.agents.base import BaseAgent
from text_mate_backend.utils.configuration import Configuration


class SocialMediaAgent(BaseAgent):
    """Agent for creating social media content."""

    def __init__(
        self,
        config: Configuration,
        platform: str = "general",
        **kwargs,
    ):
        self.platform = platform
        super().__init__(config, **kwargs)

    def get_name(self) -> str:
        return "SocialMedia"

    def get_system_prompt(self) -> str:
        platform_guidelines = {
            'twitter': 'Twitter/X - Keep it under 280 characters, use relevant hashtags, make it engaging and shareable.',
            'linkedin': 'LinkedIn - Professional tone, focus on industry insights and value, include relevant professional hashtags.',
            'instagram': 'Instagram - Visual-first mindset, include engaging caption with relevant hashtags and emojis.',
            'facebook': 'Facebook - Conversational tone, encourage engagement, can be longer than other platforms.',
            'general': 'General social media - Adapt to platform conventions, keep it engaging and shareable.',
        }.get(self.platform, 'Adapt to the platform conventions.')

        return f"""
        You are a social media content creator specializing for {self.platform}.
        
        {platform_guidelines}
        
        Guidelines:
        - Make the content engaging and shareable
        - Adapt the tone to the platform and target audience
        - The rewritten text should be in same language as input text
        - Format as markdown, don't use HTML tags
        - Don't include any introductory or closing remarks
        - Only respond with the social media post content
        """

    def _register_tools(self, agent):
        """Register social media tools."""

        @agent.tool
        async def count_characters(ctx: RunContext, text: str, platform: str = "twitter") -> dict:
            """Count characters and check platform limits."""
            limits = {
                'twitter': 280,
                'linkedin': 3000,
                'instagram': 2200,
                'facebook': 63206,
            }

            limit = limits.get(platform.lower(), 280)
            char_count = len(text)

            return {
                "character_count": char_count,
                "limit": limit,
                "within_limit": char_count <= limit,
                "remaining": limit - char_count if char_count <= limit else 0,
                "over_by": char_count - limit if char_count > limit else 0,
            }

        @agent.tool
        async def extract_hashtags(ctx: RunContext, text: str) -> list[str]:
            """Extract hashtags from text."""
            import re
            return re.findall(r'#\w+', text)

        return agent
