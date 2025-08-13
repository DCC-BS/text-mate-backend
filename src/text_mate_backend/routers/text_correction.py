from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Security
from fastapi_azure_auth.exceptions import Unauthorized
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.text_corretion_models import CorrectionInput, CorrectionResult, TextCorrectionOptions
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.text_correction_language_tool import TextCorrectionService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("text_correction_router")


@inject
def create_router(
    text_correction_service: TextCorrectionService = Provide[Container.text_correction_service],
    azure_service: AzureService = Provide[Container.azure_service],
) -> APIRouter:
    logger.info("Creating text correction router")
    router: APIRouter = APIRouter()

    azure_scheme = azure_service.azure_scheme

    @router.post("/text-correction", response_model=CorrectionResult, dependencies=[Security(azure_scheme)])
    def correct_text(input: CorrectionInput, user: User = Depends(azure_scheme)) -> CorrectionResult:
        logger.debug("Authenticated user", user=user)
        logger.debug("Roles", roles=user.roles)

        text_length = len(input.text)
        logger.debug("Text preview", text_preview=input.text[:50] + ("..." if text_length > 50 else ""))

        result = text_correction_service.correct_text(input.text, TextCorrectionOptions(language=input.language))
        return handle_result(result)

    logger.info("Text correction router configured")
    return router
