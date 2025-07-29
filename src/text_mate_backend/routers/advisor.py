from os import path
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Security
from fastapi.responses import FileResponse
from fastapi_azure_auth.user import User
from pydantic import BaseModel

from text_mate_backend.container import Container
from text_mate_backend.models.ruel_models import RuelDocumentDescription, RuelsValidationContainer
from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_router")


class AdvisorInput(BaseModel):
    text: Annotated[str, "The text to analyze and provide advice for"]
    docs: Annotated[set[str], "The documents to use for the analysis"]


@inject
def create_router(
    advisor_service: AdvisorService = Provide[Container.advisor_service],
    azure_service: AzureService = Provide[Container.azure_service],
) -> APIRouter:
    logger.info("Creating advisor router")
    router: APIRouter = APIRouter(prefix="/advisor", tags=["advisor"])

    azure_scheme = azure_service.azure_scheme

    @router.get("/docs", dependencies=[Security(azure_scheme)])
    def get_advisor_docs(
        current_user: Annotated[User, Depends(azure_service.azure_scheme)],
    ) -> list[RuelDocumentDescription]:
        return advisor_service.get_docs(current_user)

    @router.post("/validate", response_model=RuelsValidationContainer, dependencies=[Security(azure_scheme)])
    def validate_advisor(data: AdvisorInput) -> RuelsValidationContainer:
        return advisor_service.check_text(
            data.text,
            data.docs,
        )

    @router.get("/doc/{name}", dependencies=[Security(azure_scheme)])
    async def get_document(name: str) -> FileResponse:
        """
        Get the document description by name.
        """

        file_path = path.join("docs", name)

        if not path.exists(file_path):
            raise HTTPException(status_code=404, detail="Document not found")

        return FileResponse(path=file_path, media_type="application/pdf", filename=name)

    logger.info("Advisor router configured")
    return router
