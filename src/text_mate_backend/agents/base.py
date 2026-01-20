"""Base agent with comprehensive pydantic AI features."""

from abc import ABC, abstractmethod
from typing import Sequence, TypeVar, Optional, AsyncGenerator, Any
from collections.abc import Mapping, Callable

from pydantic_ai import Agent, RunContext, ModelSettings, UsageLimits
from pydantic_ai.agent.abstract import Instructions
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.agents.validators import apply_eszett_validator, apply_text_trimmer

DepsType = TypeVar('DepsType')
OutputType = TypeVar('OutputType')


class BaseAgent(ABC):
    """Abstract base class for reusable pydantic AI agents with full feature support."""

    def __init__(
        self,
        config: Configuration,
        deps_type: Optional[type[DepsType]] = None,
        output_type: Optional[type[OutputType]] = None,
        model_settings: Optional[ModelSettings] = None,
        usage_limits: Optional[UsageLimits] = None,
        retries: int | None = None,
        metadata: dict[str, Any] | Callable[[RunContext], dict[str, Any]] | None = None,
    ):
        self.config = config
        self._deps_type = deps_type
        self._output_type = output_type
        self._model_settings = model_settings
        self._usage_limits = usage_limits
        self._retries = retries
        self._metadata = metadata

        self._model = OpenAIChatModel(
            config.llm_model,
            provider=OpenAIProvider(
                base_url=config.llm_url,
                api_key=config.openai_api_key,
            ),
        )

        self._agent = self._create_agent()

    def _create_agent(self) -> Agent[DepsType, OutputType]:
        """Create and configure agent with validators."""
        agent_kwargs = {
            'model': self._model,
            'system_prompt': self.get_system_prompt(),
            'instructions': self.get_instructions(),
        }

        if self._deps_type is not None:
            agent_kwargs['deps_type'] = self._deps_type

        if self._output_type is not None:
            agent_kwargs['output_type'] = self._output_type

        if self._model_settings is not None:
            agent_kwargs['model_settings'] = self._model_settings

        if self._retries is not None:
            agent_kwargs['retries'] = self._retries

        if self._metadata is not None:
            agent_kwargs['metadata'] = self._metadata

        agent = Agent(**agent_kwargs)

        agent = self._apply_validators(agent)
        agent = self._register_tools(agent)
        agent = self._register_instructions(agent)

        return agent

    def _apply_validators(self, agent: Agent[DepsType, OutputType]) -> Agent[DepsType, OutputType]:
        """Apply common validators to the agent."""
        agent = apply_eszett_validator(agent)
        agent = apply_text_trimmer(agent)
        return agent

    def _register_tools(self, agent: Agent[DepsType, OutputType]) -> Agent[DepsType, OutputType]:
        """Register agent-specific tools. Override in subclasses."""
        return agent

    def _register_instructions(self, agent: Agent[DepsType, OutputType]) -> Agent[DepsType, OutputType]:
        return agent

    @abstractmethod
    def get_name(self) -> str:
        """Return the agent's name."""
        pass

    def get_system_prompt(self) -> str | Sequence[str]:
        """Return the agent's system prompt."""
        return ()

    def get_instructions(self) -> Instructions:
        return None

    async def run(
        self,
        user_prompt: str,
        deps: Optional[DepsType] = None,
        model_settings: Optional[ModelSettings] = None,
        usage_limits: Optional[UsageLimits] = None,
        message_history: Optional[list] = None,
    ) -> OutputType:
        """Run the agent and return structured output."""
        result = await self._agent.run(
            user_prompt + " /no_think",
            deps=deps,
            model_settings=model_settings,
            usage_limits=usage_limits,
            message_history=message_history,
        )
        return result.output

    def run_sync(
        self,
        user_prompt: str,
        deps: Optional[DepsType] = None,
        model_settings: Optional[ModelSettings] = None,
        usage_limits: Optional[UsageLimits] = None,
        message_history: Optional[list] = None,
    ) -> OutputType:
        """Synchronous version of run()."""
        result = self._agent.run_sync(
            user_prompt + " /no_think",
            deps=deps,
            model_settings=model_settings,
            usage_limits=usage_limits,
            message_history=message_history,
        )
        return result.output

    async def run_stream(
        self,
        user_prompt: str,
        deps: Optional[DepsType] = None,
        model_settings: Optional[ModelSettings] = None,
        usage_limits: Optional[UsageLimits] = None,
        message_history: Optional[list] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream agent execution text output."""
        async with self._agent.run_stream(
            user_prompt + " /no_think",
            deps=deps,
            model_settings=model_settings,
            usage_limits=usage_limits,
            message_history=message_history,
        ) as result:
            async for event in result.stream_text():
                yield event

    async def run_stream_events(
        self,
        user_prompt: str,
        deps: Optional[DepsType] = None,
        model_settings: Optional[ModelSettings] = None,
        usage_limits: Optional[UsageLimits] = None,
        message_history: Optional[list] = None,
    ):
        """Stream all events from the agent run."""
        async for event in self._agent.run_stream_events(
            user_prompt + " /no_think",
            deps=deps,
            model_settings=model_settings,
            usage_limits=usage_limits,
            message_history=message_history,
        ):
            yield event

    def iter(self, user_prompt: str, deps: Optional[DepsType] = None):
        """Iterate over the agent's graph nodes."""
        return self._agent.iter(user_prompt + " /no_think", deps=deps)
