from typing import TypeVar

from fastapi import HTTPException
from returns.result import Failure, Result, Success

from text_mate_backend.utils.logger import get_logger

T = TypeVar("T")
logger = get_logger()


def handle_result(result: Result[T, Exception]) -> T:
    """
    Handles an Either result by returning the value or raising an HTTPException with the error message.

    Args:
        result: The Either monad containing either an error message or a successful value

    Returns:
        The value from the Either if successful

    Raises:
        HTTPException: If the Either contains an error
    """

    match result:
        case Failure(error):
            logger.error(f"{error}")
            raise HTTPException(status_code=400, detail=str(error))
        case Success(value):
            return value  # type: ignore
        case _:
            raise HTTPException(status_code=500, detail="Unknown error")
