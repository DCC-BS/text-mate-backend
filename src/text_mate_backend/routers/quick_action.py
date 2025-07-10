from authentication import AzureAdTokenPayload, get_current_user
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from returns.result import Failure, Success

from text_mate_backend.container import Container
from text_mate_backend.models.quick_actions_models import QuickActionRequest
from text_mate_backend.services.actions.quick_action_service import QuickActionService
from text_mate_backend.utils.logger import get_logger

logger = get_logger("quick_action_router")


@inject
def create_router(quick_action_service: QuickActionService = Provide[Container.quick_action_service]) -> APIRouter:
    logger.info("Creating quick action router")
    router: APIRouter = APIRouter(prefix="/quick-action", tags=["quick-action"])

    @router.post("")
    def quick_action(
        request: QuickActionRequest, current_user: AzureAdTokenPayload = Depends(get_current_user)
    ) -> StreamingResponse:
        text_length = len(request.text)

        logger.info("Quick action request received", action=request.action, text_length=text_length)
        logger.debug(
            "Quick action request details", text_preview=request.text[:50] + ("..." if text_length > 50 else "")
        )

        logger.debug("The user is ", user=current_user)

        result = quick_action_service.run(request.action, request.text)

        match result:
            case Success(value):
                logger.info(f"Quick action '{request.action}' completed successfully")
                return value  # type: ignore
            case Failure(error):
                logger.error(f"Quick action '{request.action}' failed", error=str(error))
                raise HTTPException(status_code=400, detail=str(error))
            case _:
                logger.error(f"Quick action '{request.action}' failed with unknown error")
                raise HTTPException(status_code=500, detail="Unknown error")

    logger.info("Quick action router configured")
    return router
