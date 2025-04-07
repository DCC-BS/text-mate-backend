from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter
from pydantic import BaseModel

from text_mate_backend.container import Container
from text_mate_backend.models.text_rewrite_models import RewriteResult, TextRewriteOptions
from text_mate_backend.routers.utils import handle_result
from text_mate_backend.services.rewrite_text import TextRewriteService


class RewriteInput(BaseModel):
    text: Annotated[str, "The original text to be rewritten"]
    context: Annotated[str, "Additional context to guide the text rewriting"]
    writing_style: Annotated[str, "The desired writing style for the rewritten text"] = "general"
    target_audience: Annotated[str, "The target audience for the rewritten text"] = "general"
    intend: Annotated[str, "The purpose or intention of the text"] = "general"


@inject
def create_router(text_rewrite_service: TextRewriteService = Provide[Container.text_rewrite_service]) -> APIRouter:
    router: APIRouter = APIRouter(prefix="/text-rewrite", tags=["text-rewrite"])

    @router.post("", response_model=RewriteResult)
    def rewrite_text(data: RewriteInput) -> RewriteResult:
        options: TextRewriteOptions = TextRewriteOptions(
            writing_style=data.writing_style, target_audience=data.target_audience, intend=data.intend
        )

        result = text_rewrite_service.rewrite_text(data.text, data.context, options)
        return handle_result(result)

    return router
