from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.params import Security
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.text_rewrite_models import RewriteInput, RewriteResult
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.rewrite_text import TextRewriteService
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id

logger = get_logger("text_rewrite_router")


@inject
def create_router(
    text_rewrite_service: TextRewriteService = Provide[Container.text_rewrite_service],
    azure_service: AzureService = Provide[Container.azure_service],
    config: Configuration = Provide[Container.config],
) -> APIRouter:
    logger.info("Creating text rewrite router")
    router: APIRouter = APIRouter(prefix="/text-rewrite", tags=["text-rewrite"])

    azure_scheme = azure_service.azure_scheme

    @router.post("", response_model=RewriteResult, dependencies=[Security(azure_scheme)])
    def rewrite_text(
        data: RewriteInput,
        current_user: Annotated[User, Depends(azure_service.azure_scheme)],
    ) -> RewriteResult:
        pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)
        text_length = len(data.text)
        context_length = len(data.context)

        logger.info(
            "app_event",
            extra={
                "pseudonym_id": pseudonymized_user_id,
                "event": rewrite_text.__name__,
                "text_length": text_length,
                "context_length": context_length,
                "writing_style": data.writing_style,
                "target_audience": data.target_audience,
                "intend": data.intend,
            },
        )

        result = text_rewrite_service.rewrite_text(data.text, data.context, data.options)
        return handle_result(result)

    logger.info("Text rewrite router configured")
    return router
