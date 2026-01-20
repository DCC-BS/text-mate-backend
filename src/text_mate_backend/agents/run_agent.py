from typing import Any
from dcc_backend_common.logger import get_logger
from pydantic_ai import Agent
from pydantic_ai.result import StreamedRunResult
from text_mate_backend.agents.replace_eszett import replace_eszett

logger = get_logger()

async def run_stream_text2(agent: Agent, prompt: str, **args: dict[str, Any]):
    async with agent.run_stream(user_prompt=prompt, *args) as result:
        async for chunk in result.stream_text(delta=True):
            yield replace_eszett(chunk)

async def run_stream_output(agent: Agent, prompt: str, **args: dict[str, Any]):
    async with agent.run_stream(user_prompt=prompt, *args) as result:
        async for chunk in result. stream_output():
            yield replace_eszett(chunk)



async def run_stream_text(stream_result: StreamedRunResult[None, str]):
    async for chunk in stream_result.stream_text(delta=True):
        yield replace_eszett(chunk)
