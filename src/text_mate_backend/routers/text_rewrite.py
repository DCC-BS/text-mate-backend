from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter
from fastapi.params import Security

from text_mate_backend.container import Container
from text_mate_backend.models.text_rewrite_models import RewriteInput, RewriteResult, TextRewriteOptions
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.rewrite_text import TextRewriteService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("text_rewrite_router")


@inject
def create_router(
    text_rewrite_service: TextRewriteService = Provide[Container.text_rewrite_service],
    azure_service: AzureService = Provide[Container.azure_service],
) -> APIRouter:
    logger.info("Creating text rewrite router")
    router: APIRouter = APIRouter(prefix="/text-rewrite", tags=["text-rewrite"])

    azure_scheme = azure_service.azure_scheme

    @router.post("", response_model=RewriteResult, dependencies=[Security(azure_scheme)])
    def rewrite_text(data: RewriteInput) -> RewriteResult:
        text_length = len(data.text)
        context_length = len(data.context)

        logger.info(
            "Text rewrite request received",
            text_length=text_length,
            context_length=context_length,
            writing_style=data.writing_style,
            target_audience=data.target_audience,
            intend=data.intend,
        )
        logger.debug(
            "Request details",
            text_preview=data.text[:50] + ("..." if text_length > 50 else ""),
            context_preview=data.context[:50] + ("..." if context_length > 50 else ""),
        )

        options: TextRewriteOptions = TextRewriteOptions(
            writing_style=data.writing_style, target_audience=data.target_audience, intend=data.intend
        )

        result = text_rewrite_service.rewrite_text(data.text, data.context, options)
        return handle_result(result)

    logger.info("Text rewrite router configured")
    return router
