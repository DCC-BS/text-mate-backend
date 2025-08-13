import time
from typing import Awaitable, Callable

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, _StreamingResponse
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse

from text_mate_backend.utils.logger import get_logger

logger = get_logger("middleware")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging request and response information.

    This middleware logs:
    - Request method and path
    - Request processing time
    - Response status code
    - Client IP address

    If debug level is enabled, it also logs:
    - Request headers
    - Request body (if available)
    - Response body (if available)
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Process the request and log information about it."""
        request_id = f"req-{time.time()}"
        start_time = time.time()

        # Extract basic request info
        method = request.method
        url = str(request.url)

        # Process the request and capture any errors
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            status_code = response.status_code

            # Log successful response
            if status_code >= 400:
                match response:
                    case JSONResponse() as json_response:
                        response_body = repr(json_response.body)
                    case StreamingResponse() | _StreamingResponse():
                        response_body = "Streaming response"
                    case PlainTextResponse() as text_response if isinstance(text_response.body, bytes):
                        response_body = text_response.body.decode("utf-8")
                    case _:
                        response_body = f"Unknown response type {type(response)}"

                # Log error responses
                logger.warning(
                    "Request resulted in error",
                    response_body=response_body,
                    request_id=request_id,
                    method=method,
                    url=url,
                    status_code=status_code,
                    process_time=f"{process_time:.3f}s",
                )

            return response

        except Exception as e:
            # Log exceptions
            process_time = time.time() - start_time
            logger.error(
                "Request failed",
                request_id=request_id,
                method=method,
                url=url,
                error=str(e),
                error_type=type(e).__name__,
                process_time=f"{process_time:.3f}s",
                exc_info=True,
            )
            raise


def add_logging_middleware(app: FastAPI) -> None:
    """Add the logging middleware to a FastAPI application."""
    app.add_middleware(LoggingMiddleware)
    logger.info("Logging middleware configured")
