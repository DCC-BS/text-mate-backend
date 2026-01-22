"""Base agent with comprehensive pydantic AI features."""

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, AsyncGenerator, Sequence, TypeAlias, TypedDict, TypeVar

from dcc_backend_common.logger import get_logger
from pydantic_ai import Agent, AgentRunResult, UserContent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.result import StreamedRunResult

from text_mate_backend.agents.postprocessing import PostprocessingContext, replace_eszett, trim_text
from text_mate_backend.utils.configuration import Configuration

DepsType = TypeVar("DepsType")
OutputType = TypeVar("OutputType")

logger = get_logger(__name__)

UserPrompt: TypeAlias = str | Sequence[UserContent] | None
Preprocessor: TypeAlias = Callable[[Any, PostprocessingContext], Any]


class BaseAgent[DepsType, OutputType](ABC):
    """Abstract base class for reusable pydantic AI agents with full feature support."""

    def __init__(self, config: Configuration, enable_thinking: bool = False):
        self.config = config
        self._enable_thinking = enable_thinking

        self._model = OpenAIChatModel(
            config.llm_model,
            provider=OpenAIProvider(
                base_url=config.llm_url,
                api_key=config.openai_api_key,
            ),
        )

        self._agent = self.create_agent(self._model)

    def process_prompt(self, prompt: UserPrompt, deps: DepsType):
        if prompt is None:
            return None

        return list(prompt) + [" /no_think"]

        # postfix = "" if self._enable_thinking else " /no_think"
        # return f"{prompt}{postfix}"

    def _log_result[TOutput](self, result: AgentRunResult[TOutput] | StreamedRunResult[DepsType, TOutput]):
        usage = result.usage()

        logger.info(
            "llm_call",
            extra={
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                    "tool_calls": usage.tool_calls,
                    "requests": usage.requests,
                    "details": result.usage().details,
                },
                "finish_reason": result.response.finish_reason,
            },
        )

    def _get_postprocessors(self) -> list[Preprocessor]:
        postprocessors: list[Preprocessor] = [replace_eszett]

        if OutputType is str:
            postprocessors.append(trim_text)

        return postprocessors

    def _postprocess(self, output: Any, context: PostprocessingContext) -> Any:
        for processor in self._get_postprocessors():
            output = processor(output, context)
        return output

    @abstractmethod
    def create_agent(self, model: Model) -> Agent[DepsType, OutputType]: ...

    async def run(self, user_prompt: UserPrompt = None, deps: DepsType = None) -> OutputType:
        """Run the agent and return structured output."""
        prompt = self.process_prompt(user_prompt, deps)

        result = await self._agent.run(user_prompt=prompt, deps=deps)

        context = PostprocessingContext(isParial=False, index=0)

        self._log_result(result)
        return self._postprocess(result.output, context)

    async def run_stream_text(
        self, user_prompt: UserPrompt = None, deps: DepsType = None, delta: bool = True, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream text output with optional delta parameter and postprocessing."""
        prompt = self.process_prompt(user_prompt, deps)

        async with self._agent.run_stream(user_prompt=prompt, deps=deps, **kwargs) as result:
            i = 0
            async for chunk in result.stream_text(delta=delta):
                context = PostprocessingContext(isParial=True, index=i)
                yield self._postprocess(chunk, context)
                i += 1

            self._log_result(result)

    async def stream_list[T](
        self, user_prompt: UserPrompt = None, deps: DepsType = None, **kwargs: Any
    ) -> AsyncGenerator[T, None]:
        """Stream list items one-by-one from a TypedDict container with postprocessing."""
        prompt = self.process_prompt(user_prompt, deps)

        class Container(TypedDict):
            list: list[T]

        async with self._agent.run_stream(user_prompt=prompt, output_type=Container, deps=deps, **kwargs) as result:
            logger.debug(json.dumps(result.all_messages()))

            i = 0
            async for chunk in result.stream_output():
                context = PostprocessingContext(isParial=True, index=i)
                yield self._postprocess(chunk["list"][-1], context)
                i += 1

            self._log_result(result)

    async def run_stream_output(
        self, user_prompt: UserPrompt = None, deps: DepsType = None, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """Stream full structured output with postprocessing."""
        prompt = self.process_prompt(user_prompt, deps)

        async with self._agent.run_stream(user_prompt=prompt, deps=deps, **kwargs) as result:
            logger.debug(json.dumps(result.all_messages()))

            i = 0
            async for chunk in result.stream_output():
                context = PostprocessingContext(isParial=True, index=i)
                yield self._postprocess(chunk, context)
                i += 1

            self._log_result(result)
