from typing import Annotated

from dcc_backend_common.logger import get_logger
from dcc_backend_common.usage_tracking import UsageTrackingService
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from fastapi.params import Security
from fastapi_azure_auth.user import User

from text_mate_backend.agents.agent_types.sentence_rewrite_agent import SentenceRewriteAgent
from text_mate_backend.container import Container
from text_mate_backend.models.sentence_rewrite_model import SentenceRewriteInput, SentenceRewriteResult
from text_mate_backend.routers.utils import handle_exception
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.cancel_on_disconnect import CancelOnDisconnect
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.usage_tracking import get_user_id

logger = get_logger("sentence_rewrite_router")


@inject
def create_router(
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    config: Configuration = Provide[Container.config],
    usage_tracking_service: UsageTrackingService = Provide[Container.usage_tracking_service],
) -> APIRouter:
    """
    Create and configure a FastAPI APIRouter for sentence rewriting.

    Returns:
        APIRouter: A router with the configured sentence-rewrite POST endpoint.
    """
    logger.debug("Creating sentence rewrite router")
    router: APIRouter = APIRouter(prefix="/sentence-rewrite", tags=["sentence-rewrite"])
    agent = SentenceRewriteAgent(config)

    @router.post("", response_model=SentenceRewriteResult, dependencies=[Security(auth_scheme)])
    async def rewrite_sentence(
        request: Request,
        data: SentenceRewriteInput,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> SentenceRewriteResult:
        usage_tracking_service.log_event(
            "sentence.rewrite",
            get_user_id(current_user),
            sentence_length=len(data.sentence),
            context_length=len(data.context),
        )

        try:
            async with CancelOnDisconnect(request):
                return await agent.run(deps=data)
        except Exception as exp:
            handle_exception(exp)
            raise exp

    logger.debug("Sentence rewrite router configured")
    return router
