from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter
from pydantic import BaseModel

from text_mate_backend.container import Container
from text_mate_backend.models.text_corretion_models import CorrectionResult, TextCorrectionOptions
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.text_correction_language_tool import TextCorrectionService


class CorrectionInput(BaseModel):
    text: Annotated[str, "The text to be corrected"]


@inject
def create_router(
    text_correction_service: TextCorrectionService = Provide[Container.text_correction_service],
) -> APIRouter:
    router: APIRouter = APIRouter()

    @router.post("/text-correction", response_model=CorrectionResult)
    def correct_text(
        text: CorrectionInput,
    ) -> CorrectionResult:
        result = text_correction_service.correct_text(text.text, TextCorrectionOptions())
        return handle_result(result)

    return router
