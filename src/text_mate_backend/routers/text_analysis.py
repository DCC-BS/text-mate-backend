from typing import Annotated

from dcc_backend_common.logger import get_logger
from dcc_backend_common.usage_tracking import UsageTrackingService
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from fastapi.params import Security
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.text_analysis_models import TextAnalysisInput, TextAnalysisResult
from text_mate_backend.routers.utils import handle_exception
from text_mate_backend.services.text_analysis_service import TextAnalysisService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.usage_tracking import get_user_id

logger = get_logger("text_analysis_router")


@inject
def create_router(
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    text_analysis_service: TextAnalysisService = Provide[Container.text_analysis_service],
    usage_tracking_service: UsageTrackingService = Provide[Container.usage_tracking_service],
) -> APIRouter:
    """
    Create and configure a FastAPI APIRouter for text analysis.

    Returns:
        APIRouter: A router with the configured text-analysis POST endpoint.
    """
    logger.debug("Creating text analysis router")
    router: APIRouter = APIRouter(prefix="/text-analysis", tags=["text-analysis"])

    @router.post("", response_model=TextAnalysisResult, dependencies=[Security(auth_scheme)])
    async def analyze_text(
        request: Request,
        data: TextAnalysisInput,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> TextAnalysisResult:
        usage_tracking_service.log_event(
            "text.analyze",
            get_user_id(current_user),
            text_length=len(data.text),
        )

        try:
            return await text_analysis_service.analyze(data.text)
        except Exception as exp:
            handle_exception(exp)

    logger.debug("Text analysis router configured")
    return router
