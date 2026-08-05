import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
from os import path
from typing import Annotated

from dcc_backend_common.fastapi_error_handling import ApiErrorCodes, api_error_exception
from dcc_backend_common.logger import get_logger
from dcc_backend_common.usage_tracking import UsageTrackingService
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Security
from fastapi.responses import FileResponse, StreamingResponse
from fastapi_azure_auth.user import User
from pydantic import BaseModel, Field
from starlette.status import HTTP_403_FORBIDDEN

from text_mate_backend.container import Container
from text_mate_backend.models.error_codes import NO_DOCUMENT
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.fix_models import FixRequest
from text_mate_backend.models.rule_models import RuleDocumentDescription, RulesValidationContainer
from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.services.fix_service import FixService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.usage_tracking import get_user_id

logger = get_logger("advisor_router")


class AdvisorInput(BaseModel):
    text: Annotated[str, "The text to analyze and provide advice for"]
    docs: Annotated[set[str], Field(max_length=5, description="The documents to use for the analysis")]


@inject
def create_router(
    advisor_service: AdvisorService = Provide[Container.advisor_service],
    fix_service: FixService = Provide[Container.fix_service],
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    usage_tracking_service: UsageTrackingService = Provide[Container.usage_tracking_service],
) -> APIRouter:
    logger.debug("Creating advisor router")
    router: APIRouter = APIRouter(prefix="/advisor", tags=["advisor"])

    @router.get("/docs", dependencies=[Security(auth_scheme)])
    def get_advisor_docs(
        current_user: Annotated[User | None, Depends(auth_scheme)],
    ) -> list[RuleDocumentDescription]:
        return advisor_service.get_docs(current_user)

    @router.post("/validate", dependencies=[Security(auth_scheme)])
    async def validate_advisor(
        data: AdvisorInput,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> AsyncIterable[RulesValidationContainer]:
        usage_tracking_service.log_event(
            "advisor.validate",
            get_user_id(current_user),
            text_length=len(data.text),
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
        data: FixRequest,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> StreamingResponse:
        usage_tracking_service.log_event(
            "advisor.fix",
            get_user_id(current_user),
            text_length=len(data.text),
            thread_count=len(data.threads),
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
    async def get_document(name: str, current_user: Annotated[User, Depends(auth_scheme)]) -> FileResponse:
        """
        Get the document description by name.
        """
        safe_name = path.basename(name)

        usage_tracking_service.log_event("advisor.get_document", get_user_id(current_user), document_name=safe_name)

        file_path = path.join("assets/docs", safe_name)

        if not advisor_service.can_access_document(safe_name, current_user):
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="User does not have access to this document")

        if not path.exists(file_path):
            raise ApiErrorException({"status": 404, "errorId": NO_DOCUMENT, "debugMessage": "Document not found"})

        return FileResponse(path=file_path, media_type="application/pdf", filename=safe_name)

    logger.debug("Advisor router configured")
    return router
