from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from fastapi.params import Security
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.sentence_rewrite_model import SentenceRewriteInput, SentenceRewriteResult
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.sentence_rewrite_service import SentenceRewriteService
from text_mate_backend.utils.cancel_on_disconnect import CancelOnDisconnect
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id

logger = get_logger("sentence_rewrite_router")


@inject
def create_router(
    sentence_rewrite_service: SentenceRewriteService = Provide[Container.sentence_rewrite_service],
    azure_service: AzureService = Provide[Container.azure_service],
    config: Configuration = Provide[Container.config],
) -> APIRouter:
    """
    Create and configure a FastAPI APIRouter for sentence rewriting.
    
    The router is mounted at "/sentence-rewrite" and exposes a POST endpoint that accepts a SentenceRewriteInput,
    requires Azure authentication, and returns a SentenceRewriteResult containing rewrite options. The endpoint
    pseudonymizes the authenticated user for telemetry, invokes the SentenceRewriteService to produce rewrite
    options for the provided sentence and context, and maps those options into the response structure while
    respecting client disconnects.
    
    Returns:
        APIRouter: A router with the configured sentence-rewrite POST endpoint.
    """
    logger.info("Creating sentence rewrite router")
    router: APIRouter = APIRouter(prefix="/sentence-rewrite", tags=["sentence-rewrite"])

    azure_scheme = azure_service.azure_scheme

    @router.post("", response_model=SentenceRewriteResult, dependencies=[Security(azure_scheme)])
    async def rewrite_sentence(
        request: Request,
        data: SentenceRewriteInput,
        current_user: Annotated[User, Depends(azure_service.azure_scheme)],
    ) -> SentenceRewriteResult:
        """
        Handle an incoming sentence rewrite request, invoke the rewrite service, and return the service options wrapped in a SentenceRewriteResult.
        
        Parameters:
            data (SentenceRewriteInput): Input payload containing `sentence` (the text to rewrite) and `context` (additional context to guide rewriting).
            current_user (User): Authenticated user; a pseudonymized user id is recorded for telemetry.
        
        Returns:
            SentenceRewriteResult: Result model containing a list of rewrite option strings produced by the service.
        """
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

        async with CancelOnDisconnect(request):
            result = sentence_rewrite_service.rewrite_sentence(data.sentence, data.context).map(
                lambda options: SentenceRewriteResult(options=list(options))
            )

            return handle_result(result)

    logger.info("Sentence rewrite router configured")
    return router