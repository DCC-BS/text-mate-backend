from typing import Any, TypeVar, overload
from collections.abc import Mapping
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel

T = TypeVar('T')

@overload
def replace_eszett(obj: str) -> str: ...

@overload
def replace_eszett(obj: BaseModel) -> BaseModel: ...

@overload
def replace_eszett(obj: Mapping[Any, Any]) -> dict[Any, Any]: ...

@overload
def replace_eszett(obj: list[Any]) -> list[Any]: ...

@overload
def replace_eszett(obj: T) -> T: ...

def replace_eszett(obj: Any) -> Any:
    """Recursively replace ß with ss in all string fields."""
    if isinstance(obj, str):
        return obj.replace('ß', 'ss')
    elif isinstance(obj, BaseModel):
        for field_name in type(obj).model_fields:
            value = getattr(obj, field_name)
            setattr(obj, field_name, replace_eszett(value))
        return obj
    elif isinstance(obj, Mapping):
        return {k: replace_eszett(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_eszett(item) for item in obj]
    return obj

def apply_eszett_validator[T](agent: Agent[Any, T]):

    @agent.output_validator
    def preprocess_german_text(ctx: RunContext, output: T) -> T:
        if ctx.partial_output:
            return output  # Skip for streaming
        return replace_eszett(output)

    return agent
