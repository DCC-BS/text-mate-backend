import os

import structlog


def init_logger():
    if os.getenv("PROD"):
        # JSON renderer for production to be fluentbit compatible
        structlog.configure(processors=[structlog.processors.JSONRenderer()])


def get_logger() -> structlog.stdlib.BoundLogger:
    return structlog.get_logger()
