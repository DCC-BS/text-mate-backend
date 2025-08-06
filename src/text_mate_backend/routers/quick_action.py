from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import StreamingResponse
from fastapi_azure_auth.user import User
from returns.result import Failure, Success

from text_mate_backend.container import Container
from text_mate_backend.models.quick_actions_models import QuickActionRequest
from text_mate_backend.services.actions.quick_action_service import QuickActionService
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.utils.logger import get_logger
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id

logger = get_logger("quick_action_router")


@inject
def create_router(
    quick_action_service: QuickActionService = Provide[Container.quick_action_service],
    azure_service: AzureService = Provide[Container.azure_service],
) -> APIRouter:
    logger.info("Creating quick action router")
    router: APIRouter = APIRouter(prefix="/quick-action", tags=["quick-action"])

    azure_scheme = azure_service.azure_scheme
    config = Container.config()

    @router.post("", dependencies=[Security(azure_scheme)])
    def quick_action(
        request: QuickActionRequest,
        current_user: Annotated[User, Depends(azure_service.azure_scheme)],
    ) -> StreamingResponse:
        text_length = len(request.text)

        logger.info("Quick action request received", action=request.action, text_length=text_length)
        logger.debug(
            "Quick action request details", text_preview=request.text[:50] + ("..." if text_length > 50 else "")
        )

        result = quick_action_service.run(request.action, request.text)

        match result:
            case Success(value):
                pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)
                logger.info(
                    "app_event",
                    extra={
                        "pseudonym_id": pseudonymized_user_id,
                        "event": "quick_action",
                        "action": request.action,
                    },
                )
                return value  # type: ignore
            case Failure(error):
                logger.error(f"Quick action '{request.action}' failed", error=str(error))
                raise HTTPException(status_code=400, detail=str(error))
            case _:
                logger.error(f"Quick action '{request.action}' failed with unknown error")
                raise HTTPException(status_code=500, detail="Unknown error")

    logger.info("Quick action router configured")
    return router
