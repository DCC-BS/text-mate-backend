from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter

from text_mate_backend.container import Container
from text_mate_backend.models.text_corretion_models import CorrectionInput, CorrectionResult, TextCorrectionOptions
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.text_correction_language_tool import TextCorrectionService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("text_correction_router")


@inject
def create_router(
    text_correction_service: TextCorrectionService = Provide[Container.text_correction_service],
) -> APIRouter:
    logger.info("Creating text correction router")
    router: APIRouter = APIRouter()

    @router.post("/text-correction", response_model=CorrectionResult)
    def correct_text(
        text: CorrectionInput,
    ) -> CorrectionResult:
        text_length = len(text.text)
        logger.info("Text correction request received", text_length=text_length)
        logger.debug("Text preview", text_preview=text.text[:50] + ("..." if text_length > 50 else ""))

        result = text_correction_service.correct_text(text.text, TextCorrectionOptions())
        return handle_result(result)

    logger.info("Text correction router configured")
    return router
