from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from returns.result import Success, Failure

from text_mate_backend.container import Container
from text_mate_backend.services.actions.quick_action_service import Actions, QuickActionService


class QuickActionRequest(BaseModel):
    action: Annotated[Actions, "The quick action to perform"]
    text: Annotated[str, "The text to apply the action to"]


@inject
def create_router(quick_action_service: QuickActionService = Provide[Container.quick_action_service]) -> APIRouter:
    router: APIRouter = APIRouter(prefix="/quick-action", tags=["quick-action"])

    @router.post("")
    def quick_action(request: QuickActionRequest) -> StreamingResponse:
        result = quick_action_service.run(request.action, request.text)

        match result:
            case Success(value):
                return value  # type: ignore
            case Failure(error):
                raise HTTPException(status_code=400, detail=str(error))
            case _:
                raise HTTPException(status_code=500, detail="Unknown error")

    return router
