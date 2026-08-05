"""
Document Conversion API Router

This module defines the FastAPI routes for document conversion services.
It provides endpoints for converting various document formats (PDF, DOCX)
to markdown with image extraction capabilities.
"""

import asyncio
from typing import Annotated

from dcc_backend_common.logger import get_logger
from dcc_backend_common.usage_tracking import UsageTrackingService
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Security, UploadFile
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.conversion_result import ConversionResult
from text_mate_backend.services.document_conversion_service import DocumentConversionService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.usage_tracking import get_user_id

logger = get_logger("convert_router")


@inject
def create_router(
    document_conversion_service: DocumentConversionService = Provide[Container.document_conversion_service],
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    usage_tracking_service: UsageTrackingService = Provide[Container.usage_tracking_service],
) -> APIRouter:
    """
    Create and configure the document conversion API router.

    Args:
        document_conversion_service: Injected document conversion service instance

    Returns:
        APIRouter: Configured router with conversion endpoints
    """
    logger.debug("Creating convert router")
    router: APIRouter = APIRouter(prefix="/convert", tags=["convert"])

    @router.post("/doc", summary="Convert document to markdown", dependencies=[Security(auth_scheme)])
    async def convert(
        request: Request,
        file: UploadFile,
        current_user: Annotated[User, Depends(auth_scheme)],
    ) -> ConversionResult:
        """
        Convert the content of an uploaded document to markdown with images.

        This endpoint accepts various document formats (PDF, DOCX) and converts
        them to markdown format while extracting and encoding any embedded images.

        Args:
            file: Uploaded document file to convert

        Returns:
            ConversionResult: Conversion result with markdown content and images
        """

        usage_tracking_service.log_event(
            "document.convert",
            get_user_id(current_user),
            file_size=file.size,
            content_type=file.content_type,
        )

        task = asyncio.create_task(document_conversion_service.convert(file))

        while task.done() is False:
            await asyncio.sleep(0.1)
            if await request.is_disconnected():
                task.cancel()
                logger.info("Conversion task cancelled due to client disconnect")
                return ConversionResult(html="")
        result = task.result()
        return ConversionResult(html=result.html)

    logger.debug("Conversion router configured")
    return router
