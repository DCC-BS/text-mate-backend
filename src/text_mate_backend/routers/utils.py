from typing import NoReturn

from dcc_backend_common.logger import get_logger

from text_mate_backend.models.error_response import ApiErrorException

logger = get_logger("router_utils")


def handle_exception(exp: Exception, request_id: str | None = None) -> NoReturn:

    log_context = {"request_id": request_id} if request_id else {}

    error_type = type(exp).__name__
    error_message = str(exp)

    logger.error(
        f"Operation failed: {error_type}",
        error_message=error_message,
        error_type=error_type,
        exc_info=exp,
        **log_context,
    )

    raise ApiErrorException(
        {
            "status": 400,
            "errorId": error_type,
            "debugMessage": error_message,
        }
    ) from exp
