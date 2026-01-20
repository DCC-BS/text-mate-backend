from collections.abc import AsyncGenerator
from typing import Type, TypeVar

from pydantic_ai import Agent
from pydantic_ai.agent.abstract import _system_prompt
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from text_mate_backend.models.error_response import TypedDict
from text_mate_backend.utils.configuration import Configuration

T = TypeVar("T")


class PydanticAIAgent:
    """Async facade wrapping Pydantic AI Agent with new agent structure"""

    def __init__(self, config: Configuration) -> None:
        self.config = config

        # Create OpenAI-compatible model with custom provider (for backward compatibility)
        self.model = OpenAIChatModel(
            config.llm_model,
            provider=OpenAIProvider(
                base_url=config.llm_url,
                api_key=config.openai_api_key,
            ),
        )
        self.agent = Agent(self.model)

    async def run[T](self, promt: str, response_type: Type[T] = str) -> T:
        agent = Agent[None, T](self.model, output_type=response_type)
        result = await agent.run(promt + " /no_think")
        return result.output

    async def stream_text[T](self, promt: str, delta=True) -> AsyncGenerator[str, None]:
        agent = Agent(
            self.model,
        )

        async with agent.run_stream(promt + " /no_think") as result:
            async for chunk in result.stream_text(delta=delta):
                yield chunk

    async def stream[T](self, prompt: str, response_type: Type[T]) -> AsyncGenerator[T, None]:
        agent = Agent[None, T](self.model, output_type=response_type)

        async with agent.run_stream(prompt  + " /no_think") as result:
            async for chunk in result.stream_output():
                yield chunk

    async def steam_list[T](self, promt: str) -> AsyncGenerator[T, None]:
        class Container(TypedDict):
            list: list[T]

        agent = Agent[None, Container](self.model, output_type=Container)

        async with agent.run_stream(promt + " /no_think") as result:
            async for chunk in result.stream_output():
                yield chunk["list"][-1]
