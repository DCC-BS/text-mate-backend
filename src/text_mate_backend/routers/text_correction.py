from typing import Annotated

from dcc_backend_common.logger import get_logger
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Security
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.text_corretion_models import CorrectionInput, CorrectionResult, TextCorrectionOptions
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.text_correction_language_tool import TextCorrectionService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.cancel_on_disconnect import CancelOnDisconnect
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id

logger = get_logger("text_correction_router")


@inject
def create_router(
    text_correction_service: TextCorrectionService = Provide[Container.text_correction_service],
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    config: Configuration = Provide[Container.config],
) -> APIRouter:
    logger.info("Creating text correction router")
    router: APIRouter = APIRouter()

    @router.post("/text-correction", response_model=CorrectionResult, dependencies=[Security(auth_scheme)])
    async def correct_text(
        request: Request,
        input: CorrectionInput,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> CorrectionResult:
        pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)

        text_length = len(input.text)
        logger.info(
            "app_event",
            extra={
                "pseudonym_id": pseudonymized_user_id,
                "event": correct_text.__name__,
                "text_length": text_length,
                "language": input.language,
            },
        )

        async with CancelOnDisconnect(request):
            result = text_correction_service.correct_text(input.text, TextCorrectionOptions(language=input.language))
            return handle_result(result)

    logger.info("Text correction router configured")
    return router
