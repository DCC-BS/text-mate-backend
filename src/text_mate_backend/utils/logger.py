import os
from typing import Optional

import structlog
from structlog.stdlib import BoundLogger


def init_logger() -> None:
    """
    Initialize the logger configuration based on environment.
    Uses JSON renderer in production environment for compatibility with fluentbit.
    """
    if os.getenv("PROD"):
        # JSON renderer for production to be fluentbit compatible
        structlog.configure(processors=[structlog.processors.JSONRenderer()])


def get_logger() -> BoundLogger:
    """
    Get a structured logger instance.

    Returns:
        A bound logger instance for structured logging
    """
    return structlog.get_logger()  # type: ignore
