from collections.abc import Generator
from os import path
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from fastapi.params import Security
from fastapi.responses import FileResponse, StreamingResponse
from fastapi_azure_auth.user import User
from pydantic import BaseModel

from text_mate_backend.container import Container
from backend_common.fastapi_error_handling import ApiErrorException
from text_mate_backend.models.rule_models import RuelDocumentDescription
from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id
from text_mate_backend.models.error_codes import TextMateApiErrorCodes


logger = get_logger("advisor_router")


class AdvisorInput(BaseModel):
    text: Annotated[str, "The text to analyze and provide advice for"]
    docs: Annotated[set[str], "The documents to use for the analysis"]


@inject
def create_router(
    advisor_service: AdvisorService = Provide[Container.advisor_service],
    azure_service: AzureService = Provide[Container.azure_service],
    config: Configuration = Provide[Container.config],
) -> APIRouter:
    logger.info("Creating advisor router")
    router: APIRouter = APIRouter(prefix="/advisor", tags=["advisor"])

    azure_scheme = azure_service.azure_scheme

    @router.get("/docs", dependencies=[Security(azure_scheme)])
    def get_advisor_docs(
        current_user: Annotated[User, Depends(azure_service.azure_scheme)],
    ) -> list[RuelDocumentDescription]:
        return advisor_service.get_docs(current_user)

    @router.post("/validate", dependencies=[Security(azure_scheme)])
    async def validate_advisor(
        request: Request,
        data: AdvisorInput,
        current_user: Annotated[User, Depends(azure_service.azure_scheme)],
    ) -> StreamingResponse:
        pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)
        logger.info(
            "app_event",
            extra={
                "pseudonym_id": pseudonymized_user_id,
                "event": validate_advisor.__name__,
                "text_length": len(data.text),
            },
        )

        def event_generator() -> Generator[str, None, None]:
            # NOTE: CancelOnDisconnect is not used here because StreamingResponse evaluation
            # happens after this handler returns. Disconnections will be handled by the ASGI server.
            for validation_result in advisor_service.check_text_stream(
                data.text,
                data.docs,
            ):
                # Each SSE event contains a single RulesValidationContainer as JSON
                yield f"data: {validation_result.model_dump_json()}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @router.get("/doc/{name}", dependencies=[Security(azure_scheme)])
    async def get_document(name: str) -> FileResponse:
        """
        Get the document description by name.
        """

        file_path = path.join("docs", name)

        if not path.exists(file_path):
            raise ApiErrorException({"status": 404, "errorId": TextMateApiErrorCodes.NO_DOCUMENT, "debugMessage": "Document not found"})

        return FileResponse(path=file_path, media_type="application/pdf", filename=name)

    logger.info("Advisor router configured")
    return router
