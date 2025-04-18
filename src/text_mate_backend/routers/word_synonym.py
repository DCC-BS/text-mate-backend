from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter

from text_mate_backend.container import Container
from text_mate_backend.models.word_synonym_models import WordSynonymInput, WordSynonymResult
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.word_synonym_service import WordSynonymService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("word_synonym_router")


@inject
def create_router(word_synonym_service: WordSynonymService = Provide[Container.word_synonym_service]) -> APIRouter:
    logger.info("Creating word synonym router")
    router: APIRouter = APIRouter(prefix="/word-synonym", tags=["word-synonym"])

    @router.post("", response_model=WordSynonymResult)
    def get_word_synonyms(data: WordSynonymInput) -> WordSynonymResult:
        logger.info(
            "Word synonym request received",
            word=data.word,
            context=data.context,
        )
        result = word_synonym_service.get_synonyms(data.word, data.context).map(
            lambda synonyms: WordSynonymResult(synonyms=synonyms)
        )

        return handle_result(result)

    logger.info("Word synonym router configured")
    return router
