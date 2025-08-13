from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter
from fastapi.params import Security

from text_mate_backend.container import Container
from text_mate_backend.models.sentence_rewrite_model import SentenceRewriteInput, SentenceRewriteResult
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.sentence_rewrite_service import SentenceRewriteService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("sentence_rewrite_router")


@inject
def create_router(
    sentence_rewrite_service: SentenceRewriteService = Provide[Container.sentence_rewrite_service],
    azure_service: AzureService = Provide[Container.azure_service],
) -> APIRouter:
    logger.info("Creating sentence rewrite router")
    router: APIRouter = APIRouter(prefix="/sentence-rewrite", tags=["sentence-rewrite"])

    azure_scheme = azure_service.azure_scheme

    @router.post("", response_model=SentenceRewriteResult, dependencies=[Security(azure_scheme)])
    def rewrite_sentence(data: SentenceRewriteInput) -> SentenceRewriteResult:
        result = sentence_rewrite_service.rewrite_sentence(data.sentence, data.context).map(
            lambda options: SentenceRewriteResult(options=options)
        )

        return handle_result(result)

    logger.info("Sentence rewrite router configured")
    return router
