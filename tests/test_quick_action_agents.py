"""Quick-action agents driven against pydantic-ai's TestModel.

No network: the real Agent, the per-run ``instructions`` and ``metadata`` callables
and the streaming path the quick-action service uses (``run_stream_text``).
"""

import asyncio

from pydantic_ai import capture_run_messages
from pydantic_ai.messages import ModelRequest
from pydantic_ai.models.test import TestModel

from text_mate_backend.agents.agent_types.quick_actions.condense_agent import CondenseAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration


def fake_config() -> Configuration:
    return Configuration(
        llm_model="test-model",
        llm_url="http://localhost:8001/v1",
        llm_api_key="test",
        llm_timeout=1,
        llm_max_retries=0,
        azure_client_id="",
        azure_tenant_id="",
        azure_frontend_client_id="",
        hmac_secret="test",
    )


def make_context() -> QuickActionContext[None]:
    return QuickActionContext(text="Ein langer, weitschweifiger Text.", options="", language="de")


async def collect(agent: CondenseAgent, context: QuickActionContext[None]) -> str:
    chunks = [chunk async for chunk in agent.run_stream_text(user_prompt=context.text, deps=context)]
    return "".join(chunks)


def test_stream_text_yields_model_output_with_swiss_orthography() -> None:
    agent = CondenseAgent(fake_config())

    with agent._agent.override(model=TestModel(custom_output_text="Die Straße ist kurz.")):
        output = asyncio.run(collect(agent, make_context()))

    assert output == "Die Strasse ist kurz."


def test_instructions_combine_agent_prompt_and_output_rules() -> None:
    agent = CondenseAgent(fake_config())

    with (
        capture_run_messages() as messages,
        agent._agent.override(model=TestModel(custom_output_text="Kurz.")),
    ):
        asyncio.run(collect(agent, make_context()))

    requests = [m for m in messages if isinstance(m, ModelRequest)]
    assert requests
    instructions = requests[0].instructions or ""
    assert "verdichten" in instructions
    assert "Gib nur reinen Text aus" in instructions


def test_run_metadata_describes_the_quick_action() -> None:
    agent = CondenseAgent(fake_config())
    context = make_context()

    with agent._agent.override(model=TestModel(custom_output_text="Kurz.")):
        result = asyncio.run(agent._agent.run(context.text, deps=context))

    assert result.metadata is not None
    assert result.metadata["component"] == "quick_action"
    assert result.metadata["action"] == agent.agent_name
    assert result.metadata["language"] == "de"
    assert result.metadata["text_length"] == len(context.text)
