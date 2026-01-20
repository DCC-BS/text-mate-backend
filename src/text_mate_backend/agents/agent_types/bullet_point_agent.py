"""Bullet point agent for converting text to bullet points."""

from text_mate_backend.agents.factory import create_agent
from text_mate_backend.utils.configuration import Configuration

def get_bulletpoint_agent(config: Configuration):

    instruction = """
        You are an assistant that converts text into a well-structured bullet point format.
        Extract and highlight key points from text.

        Convert to following text into a structured bullet point format.
        Identify and organize main ideas and supporting points.
        The bullet points should be in the same language as the input text.
        Use markdown formatting for bullet points.
        """

    return create_agent(config, output_type=str, instructions=instruction)
