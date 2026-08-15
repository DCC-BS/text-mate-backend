from typing import Annotated, Optional

from dcc_backend_common.logger import get_logger
from dcc_backend_common.usage_tracking import UsageTrackingService
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.error_codes import UNEXPECTED_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.quick_actions_models import Actions, CurrentUser, QuickActionRequest
from text_mate_backend.services.actions.quick_action_service import QuickActionService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.usage_tracking import get_user_id

logger = get_logger("quick_action_router")


@inject
def create_router(
    quick_action_service: QuickActionService = Provide[Container.quick_action_service],
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    usage_tracking_service: UsageTrackingService = Provide[Container.usage_tracking_service],
) -> APIRouter:
    logger.debug("Creating quick action router")
    router: APIRouter = APIRouter(prefix="/quick-action", tags=["quick-action"])

    @router.post("", dependencies=[Depends(auth_scheme)])
    async def quick_action(
        request: QuickActionRequest,
        current_user: Annotated[Optional[User], Depends(auth_scheme)],
    ) -> StreamingResponse:
        text_length = len(request.text)

        user: CurrentUser = {
            "email": current_user.email
            if current_user is not None and current_user.email is not None
            else "hans.muster@example.com",
            "family_name": current_user.family_name
            if current_user is not None and current_user.family_name is not None
            else "Muster",
            "given_name": current_user.given_name
            if current_user is not None and current_user.given_name is not None
            else "Hans",
        }

        if current_user is not None:
            try:
                action = request.action if isinstance(request.action, Actions) else Actions(request.action)
            except ValueError:
                # Unknown actions raise in the service below; logging them would
                # put arbitrary user strings into the low-cardinality action field.
                action = None
            if action is not None:
                usage_tracking_service.log_event(
                    f"quick_action.{action.value}",
                    get_user_id(current_user),
                    options=request.options or None,
                    text_length=text_length,
                )

        try:
            return await quick_action_service.run(request.action, request.text, request.options, user)
        except ApiErrorException:
            raise
        except Exception as e:
            logger.exception("Quick action failed", action=request.action)
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": UNEXPECTED_ERROR,
                    "debugMessage": str(e),
                }
            ) from e

    logger.debug("Quick action router configured")
    return router
