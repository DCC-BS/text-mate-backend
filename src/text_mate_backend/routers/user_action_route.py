from typing import Annotated

from dcc_backend_common.logger import get_logger
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.user_action_models import UserActionGetResponse, UserActionMeta
from text_mate_backend.services.user_actions_service import UserActionService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("user-action")


@inject
def create_router(
    user_action_service: UserActionService = Provide[Container.user_actions_service],
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    config: Configuration = Provide[Container.config]
) -> APIRouter:
    logger.info("Creating user action router")
    router: APIRouter = APIRouter(prefix="/user-action", tags=["user-action"])

    @router.get("", dependencies=[Depends(auth_scheme)])
    async def user_actions(
        current_user: Annotated[User | None, Depends(auth_scheme)],
    ) -> UserActionGetResponse:
        if current_user is None:
            if config.disable_auth:
                return UserActionGetResponse(actions=[])
            
            logger.error("User is None")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")

        actions = user_action_service.get_actions(current_user)

        return UserActionGetResponse(actions=list(map(lambda x: UserActionMeta(id=x.id, name=x.name), actions)))

    logger.info("User action router configured")
    return router
