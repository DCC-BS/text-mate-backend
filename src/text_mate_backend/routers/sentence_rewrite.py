from typing import Annotated

from dcc_backend_common.logger import get_logger
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
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id

logger = get_logger("sentence_rewrite_router")


@inject
def create_router(
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    config: Configuration = Provide[Container.config],
) -> APIRouter:
    """
    Create and configure a FastAPI APIRouter for sentence rewriting.

    Returns:
        APIRouter: A router with the configured sentence-rewrite POST endpoint.
    """
    logger.info("Creating sentence rewrite router")
    router: APIRouter = APIRouter(prefix="/sentence-rewrite", tags=["sentence-rewrite"])
    agent = SentenceRewriteAgent(config)

    @router.post("", response_model=SentenceRewriteResult, dependencies=[Security(auth_scheme)])
    async def rewrite_sentence(
        request: Request,
        data: SentenceRewriteInput,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> SentenceRewriteResult:
        pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)
        logger.info(
            "app_event",
            extra={
                "pseudonym_id": pseudonymized_user_id,
                "event": rewrite_sentence.__name__,
                "sentence_length": len(data.sentence),
                "context_length": len(data.context),
            },
        )

        try:
            async with CancelOnDisconnect(request):
                return await agent.run(deps=data)
        except Exception as exp:
            handle_exception(exp)
            raise exp

    logger.info("Sentence rewrite router configured")
    return router
