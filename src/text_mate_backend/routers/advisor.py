import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
from os import path
from typing import Annotated

from dcc_backend_common.fastapi_error_handling import ApiErrorCodes, api_error_exception
from dcc_backend_common.logger import get_logger
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from fastapi.params import Security
from fastapi.responses import FileResponse, StreamingResponse
from fastapi_azure_auth.user import User
from pydantic import BaseModel, Field

from text_mate_backend.container import Container
from text_mate_backend.models.error_codes import NO_DOCUMENT
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.fix_models import FixRequest
from text_mate_backend.models.rule_models import RuleDocumentDescription, RulesValidationContainer
from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.services.fix_service import FixService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id

logger = get_logger("advisor_router")


class AdvisorInput(BaseModel):
    text: Annotated[str, "The text to analyze and provide advice for"]
    docs: Annotated[set[str], Field(max_length=5, description="The documents to use for the analysis")]


@inject
def create_router(
    advisor_service: AdvisorService = Provide[Container.advisor_service],
    fix_service: FixService = Provide[Container.fix_service],
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    config: Configuration = Provide[Container.config],
) -> APIRouter:
    logger.info("Creating advisor router")
    router: APIRouter = APIRouter(prefix="/advisor", tags=["advisor"])

    @router.get("/docs", dependencies=[Security(auth_scheme)])
    def get_advisor_docs(
        current_user: Annotated[User | None, Depends(auth_scheme)],
    ) -> list[RuleDocumentDescription]:
        return advisor_service.get_docs(current_user)

    @router.post("/validate", dependencies=[Security(auth_scheme)])
    async def validate_advisor(
        request: Request,
        data: AdvisorInput,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> AsyncIterable[RulesValidationContainer]:
        pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)

        logger.info(
            "app_event",
            extra={
                "pseudonym_id": pseudonymized_user_id,
                "event": validate_advisor.__name__,
                "text_length": len(data.text),
            },
        )

        try:
            async for validation_result in advisor_service.check_text_stream(
                data.text,
                data.docs,
            ):
                yield validation_result
        except asyncio.CancelledError:
            logger.info("Client disconnected from advisor JSON Lines stream")
            raise
        except Exception as e:
            logger.exception("Unhandled error during advisor JSON Lines stream")
            raise api_error_exception(errorId=ApiErrorCodes.UNEXPECTED_ERROR, status=500, debugMessage=str(e)) from e

    @router.post("/fix", dependencies=[Security(auth_scheme)])
    async def fix_text(
        request: Request,
        data: FixRequest,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> StreamingResponse:
        pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)

        logger.info(
            "app_event",
            extra={
                "pseudonym_id": pseudonymized_user_id,
                "event": fix_text.__name__,
                "text_length": len(data.text),
                "thread_count": len(data.threads),
            },
        )

        async def text_generator() -> AsyncGenerator[str, None]:
            # NOTE: CancelOnDisconnect is not used here because StreamingResponse evaluation
            # happens after this handler returns. Disconnects will be handled by ASGI server.
            try:
                async for chunk in fix_service.fix_text_stream(data.text, data.threads):
                    yield chunk
            except asyncio.CancelledError:
                logger.info("Client disconnected from advisor fix stream")
                raise
            except Exception:
                # The response (200 + text/plain) is already sent, so we cannot
                # signal the error to the client without corrupting the text
                # stream. Log the full traceback at the router boundary (matching
                # /validate) and re-raise so the connection closes rather than
                # completing as if nothing went wrong.
                logger.exception("Unhandled error during advisor fix stream")
                raise

        return StreamingResponse(
            text_generator(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/doc/{name}", dependencies=[Security(auth_scheme)])
    async def get_document(name: str) -> FileResponse:
        """
        Get the document description by name.
        """

        file_path = path.join("assets/docs", name)

        if not path.exists(file_path):
            raise ApiErrorException({"status": 404, "errorId": NO_DOCUMENT, "debugMessage": "Document not found"})

        return FileResponse(path=file_path, media_type="application/pdf", filename=name)

    logger.info("Advisor router configured")
    return router
