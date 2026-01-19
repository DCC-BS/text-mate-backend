from typing import TypeVar

from dcc_backend_common.logger import get_logger
from returns.result import Failure, Result, Success

from text_mate_backend.models.error_codes import UNEXPECTED_ERROR
from text_mate_backend.models.error_response import ApiErrorException

T = TypeVar("T")
logger = get_logger("router_utils")


def handle_exception(exp: Exception, request_id: str | None = None):
    log_context = {"request_id": request_id} if request_id else {}

    error_type = type(exp).__name__
    error_message = str(exp)

    logger.error(f"Operation failed: {error_type}", error_message=error_message, error_type=error_type, **log_context)

    raise ApiErrorException(
        {
            "status": 400,
            "errorId": error_type,
            "debugMessage": error_message,
        }
    ) from exp


def handle_result(result: Result[T, Exception], request_id: str | None = None) -> T:
    """
    Handles an Result monad by returning the value or raising an HTTPException with the error message.
    Also logs appropriate information for both success and failure cases.

    Args:
        result: The Result monad containing either an error or a successful value
        request_id: Optional request ID for correlation in logs

    Returns:
        The value from the Result if successful

    Raises:
        HTTPException: If the Result contains an error
    """
    log_context = {"request_id": request_id} if request_id else {}

    match result:
        case Failure(error):
            error_type = type(error).__name__
            error_message = str(error)

            logger.error(
                f"Operation failed: {error_type}", error_message=error_message, error_type=error_type, **log_context
            )

            raise ApiErrorException(
                {
                    "status": 400,
                    "errorId": error_type,
                    "debugMessage": error_message,
                }
            )

        case Success(value):
            return value

        case _:
            logger.error("Unknown result type returned", result_type=str(type(result)), **log_context)
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": UNEXPECTED_ERROR,
                    "debugMessage": "Unknown error",
                }
            )
