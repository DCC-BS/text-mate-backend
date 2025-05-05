from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter
from pydantic import BaseModel

from text_mate_backend.container import Container
from text_mate_backend.models.ruel_models import RuelsValidationContainer
from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("advisor_router")


class AdvisorInput(BaseModel):
    text: Annotated[str, "The text to analyze and provide advice for"]
    docs: Annotated[set[str], "The documents to use for the analysis"]


@inject
def create_router(advisor_service: AdvisorService = Provide[Container.advisor_service]) -> APIRouter:
    logger.info("Creating advisor router")
    router: APIRouter = APIRouter(prefix="/advisor", tags=["advisor"])

    @router.get("/docs")
    def get_advisor_docs() -> list[str]:
        return list(advisor_service.get_docs())

    @router.post("/validate", response_model=RuelsValidationContainer)
    def validate_advisor(data: AdvisorInput) -> RuelsValidationContainer:
        return advisor_service.check_text(
            data.text,
            data.docs,
        )

    logger.info("Advisor router configured")
    return router
