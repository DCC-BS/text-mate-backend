from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Security
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.word_synonym_models import WordSynonymInput, WordSynonymResult
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.word_synonym_service import WordSynonymService
from text_mate_backend.utils.logger import get_logger
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id

logger = get_logger("word_synonym_router")


@inject
def create_router(
    word_synonym_service: WordSynonymService = Provide[Container.word_synonym_service],
    azure_service: AzureService = Provide[Container.azure_service],
) -> APIRouter:
    logger.info("Creating word synonym router")
    router: APIRouter = APIRouter(prefix="/word-synonym", tags=["word-synonym"])

    azure_scheme = azure_service.azure_scheme
    config = Container.config()

    @router.post("", response_model=WordSynonymResult, dependencies=[Security(azure_scheme)])
    def get_word_synonyms(
        data: WordSynonymInput,
        current_user: Annotated[User, Depends(azure_service.azure_scheme)],
    ) -> WordSynonymResult:
        pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)
        logger.info(
            "app_event",
            extra={
                "pseudonym_id": pseudonymized_user_id,
                "event": "word_synonym",
                "context_length": len(data.context),
            },
        )
        result = word_synonym_service.get_synonyms(data.word, data.context).map(
            lambda synonyms: WordSynonymResult(synonyms=synonyms)
        )

        return handle_result(result)

    logger.info("Word synonym router configured")
    return router
