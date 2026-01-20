"""Factory for creating and managing action-specific agents."""

from turtle import mode
from typing import Any, Callable, Optional, Type
from pydantic_ai import Agent, ModelSettings, RunContext
from pydantic_ai.agent import NoneType
from pydantic_ai.agent.abstract import Instructions
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from text_mate_backend.agents.replace_eszett import replace_eszett
from text_mate_backend.agents.validators import apply_eszett_validator, apply_text_trimmer
from text_mate_backend.utils.configuration import Configuration


def create_agent[DepsType, OutputType](
    config: Configuration,
    deps_type: type[DepsType] = NoneType,
    output_type: type[OutputType] = str,
    model_settings: Optional[ModelSettings] = None,
    retries: int | None = None,
    instructions: Instructions[DepsType] = None,
    metadata: dict[str, Any] | Callable[[RunContext], dict[str, Any]] | None = None) -> Agent[DepsType, OutputType]:

        model = OpenAIChatModel(
            config.llm_model,
            provider=OpenAIProvider(
                base_url=config.llm_url,
                api_key=config.openai_api_key,
            ),
        )

        def postprocess(input: OutputType) -> OutputType:
            return replace_eszett(input)

        agent_kwargs: dict[str, Any] = {
        }

        if model_settings is not None:
            agent_kwargs['model_settings'] = model_settings

        if retries is not None:
            agent_kwargs['retries'] = retries

        if metadata is not None:
            agent_kwargs['metadata'] = metadata

        agent = Agent[DepsType, OutputType](
            model=model,
            instructions=instructions,
            output_type=output_type,
            deps_type=deps_type,
            **agent_kwargs)

        return agent
