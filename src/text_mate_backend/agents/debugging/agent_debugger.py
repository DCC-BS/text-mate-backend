from typing import Callable

from dcc_backend_common.logger import get_logger

from text_mate_backend.agents.debugging.event_debugger import create_event_debugger

logger = get_logger(__name__)


def withDebbugger[TRetrun](fn: Callable[..., TRetrun], name: str | None = None) -> Callable[..., TRetrun]:
    name = name or "UnnamedAgent"

    def wrapper(*args, **kwargs) -> TRetrun:
        return fn(*args, **kwargs, event_stream_handler=create_event_debugger(name))

    return wrapper
