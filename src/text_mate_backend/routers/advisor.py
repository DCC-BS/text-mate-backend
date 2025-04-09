from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter
from pydantic import BaseModel

from text_mate_backend.container import Container
from text_mate_backend.models.text_rewrite_models import TextRewriteOptions
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.advisor import AdvisorOutput, AdvisorService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_router")


class AdvisorInput(BaseModel):
    text: Annotated[str, "The text to analyze and provide advice for"]
    domain: Annotated[str, "The target domain for the text"] = "general"
    formality: Annotated[str, "The desired formality level for the text"] = "neutral"


@inject
def create_router(advisor_service: AdvisorService = Provide[Container.advisor_service]) -> APIRouter:
    logger.info("Creating advisor router")
    router: APIRouter = APIRouter(prefix="/advisor", tags=["advisor"])

    @router.post("", response_model=AdvisorOutput)
    def advisor(data: AdvisorInput) -> AdvisorOutput:
        text_length = len(data.text)

        logger.info("Advisor request received", text_length=text_length, domain=data.domain, formality=data.formality)
        logger.debug("Advisor request details", text_preview=data.text[:50] + ("..." if text_length > 50 else ""))

        options: TextRewriteOptions = TextRewriteOptions()

        result = advisor_service.advise_changes(data.text, options)

        processed_result = handle_result(result)
        logger.info(
            "Advisor response generated",
            formality_score=processed_result.formalityScore,
            domain_score=processed_result.domainScore,
            coherence_score=processed_result.coherenceAndStructure,
        )

        return processed_result

    logger.info("Advisor router configured")
    return router
