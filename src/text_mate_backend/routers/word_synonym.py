from typing import Annotated

from dcc_backend_common.logger import get_logger
from dcc_backend_common.usage_tracking import UsageTrackingService
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Security
from fastapi_azure_auth.user import User

from text_mate_backend.agents.agent_types.word_synonym_agent import WordSynonymAgent
from text_mate_backend.container import Container
from text_mate_backend.models.word_synonym_models import WordSynonymInput, WordSynonymResult
from text_mate_backend.routers.utils import handle_exception
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.cancel_on_disconnect import CancelOnDisconnect
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.usage_tracking import get_user_id

logger = get_logger("word_synonym_router")


@inject
def create_router(
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    config: Configuration = Provide[Container.config],
    usage_tracking_service: UsageTrackingService = Provide[Container.usage_tracking_service],
) -> APIRouter:
    """
    Create and configure the word-synonym API router.

    Returns:
        APIRouter: Configured FastAPI router with the word-synonym endpoint.
    """
    logger.debug("Creating word synonym router")
    router: APIRouter = APIRouter(prefix="/word-synonym", tags=["word-synonym"])
    agent = WordSynonymAgent(config)

    @router.post("", response_model=WordSynonymResult, dependencies=[Security(auth_scheme)])
    async def get_word_synonyms(
        request: Request,
        data: WordSynonymInput,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> WordSynonymResult:
        usage_tracking_service.log_event(
            "synonym.lookup",
            get_user_id(current_user),
            context_length=len(data.context),
        )

        try:
            async with CancelOnDisconnect(request):
                return await agent.run(deps=data)
        except Exception as err:
            handle_exception(err)
            raise err

    logger.debug("Word synonym router configured")
    return router
