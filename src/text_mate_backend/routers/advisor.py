from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter
from pydantic import BaseModel

from text_mate_backend.container import Container
from text_mate_backend.models.text_rewrite_models import TextRewriteOptions
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.advisor import AdvisorOutput, AdvisorService


class AdvisorInput(BaseModel):
    text: Annotated[str, "The text to analyze and provide advice for"]
    domain: Annotated[str, "The target domain for the text"] = "general"
    formality: Annotated[str, "The desired formality level for the text"] = "neutral"


@inject
def create_router(advisor_service: AdvisorService = Provide[Container.advisor_service]) -> APIRouter:
    router: APIRouter = APIRouter(prefix="/advisor", tags=["advisor"])

    @router.post("", response_model=AdvisorOutput)
    def advisor(data: AdvisorInput) -> AdvisorOutput:
        options: TextRewriteOptions = TextRewriteOptions()

        result = advisor_service.advise_changes(data.text, options)
        return handle_result(result)

    return router
