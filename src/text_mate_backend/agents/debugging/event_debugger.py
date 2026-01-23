from typing import AsyncIterable

from dcc_backend_common.logger import get_logger
from pydantic_ai import (
    AgentStreamEvent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
    ThinkingPartDelta,
    ToolCallPartDelta,
)
from pydantic_ai.agent.abstract import EventStreamHandler
from pydantic_ai.messages import PartEndEvent

from text_mate_backend.agents.agent_types.quick_actions.summarize_agent import RunContext

logger = get_logger(__name__)


def create_event_debugger(name: str) -> EventStreamHandler:
    async def handle_event(event: AgentStreamEvent) -> None:
        if isinstance(event, PartStartEvent):
            logger.debug(f"[Request] Starting part {event.index}: {event.part!r}", agent=name, extra=event)
        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                logger.debug(
                    f"[Request] Part {event.index} text delta: {event.delta.content_delta!r}", agent=name, extra=event
                )
            elif isinstance(event.delta, ThinkingPartDelta):
                logger.debug(
                    f"[Request] Part {event.index} thinking delta: {event.delta.content_delta!r}, extra=event",
                    agent=name,
                    extra=event,
                )
            elif isinstance(event.delta, ToolCallPartDelta):
                logger.debug(
                    f"[Request] Part {event.index} args delta: {event.delta.args_delta}, extra=event",
                    agent=name,
                    extra=event,
                )
        elif isinstance(event, FunctionToolCallEvent):
            logger.debug(
                f"[Tools] The LLM calls tool={event.part.tool_name!r} with args={event.part.args} (tool_call_id={event.part.tool_call_id!r})",
                agent=name,
                extra=event,
            )
        elif isinstance(event, FunctionToolResultEvent):
            logger.debug(
                f"[Tools] Tool call {event.tool_call_id!r} returned => {event.result.content}, agent=name, extra=event",
                extra=event,
            )
        elif isinstance(event, FinalResultEvent):
            logger.debug(
                f"[Result] The model starting producing a final result (tool_name={event.tool_name})",
                agent=name,
                extra=event,
            )
        elif isinstance(event, PartEndEvent):
            logger.debug(f"[Request] Ending part {event.index}: {event.part!r}", agent=name, extra=event)
        else:
            logger.debug(f"[Event] Unknown event type: {event!r}", extra=event)

    async def event_stream_handler(
        ctx: RunContext,
        event_stream: AsyncIterable[AgentStreamEvent],
    ):
        async for event in event_stream:
            await handle_event(event)

    return event_stream_handler
