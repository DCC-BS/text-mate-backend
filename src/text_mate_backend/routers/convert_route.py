"""
Document Conversion API Router

This module defines the FastAPI routes for document conversion services.
It provides endpoints for converting various document formats (PDF, DOCX)
to markdown with image extraction capabilities.
"""

import asyncio
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Security, UploadFile
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.conversion_result import ConversionOutput
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.document_conversion_service import DocumentConversionService
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger
from text_mate_backend.utils.usage_tracking import get_pseudonymized_user_id

logger = get_logger("convert_router")


@inject
def create_router(
    document_conversion_service: DocumentConversionService = Provide[Container.document_conversion_service],
    azure_service: AzureService = Provide[Container.azure_service],
    config: Configuration = Provide[Container.config],
) -> APIRouter:
    """
    Create and configure the document conversion API router.

    Args:
        document_conversion_service: Injected document conversion service instance

    Returns:
        APIRouter: Configured router with conversion endpoints
    """
    logger.info("Creating convert router")
    router: APIRouter = APIRouter(prefix="/convert", tags=["convert"])

    azure_scheme = azure_service.azure_scheme

    @router.post("/doc", summary="Convert document to markdown", dependencies=[Security(azure_scheme)])
    async def convert(
        request: Request,
        file: UploadFile,
        current_user: Annotated[User, Depends(azure_service.azure_scheme)],
    ) -> ConversionOutput:
        """
        Convert the content of an uploaded document to markdown with images.

        This endpoint accepts various document formats (PDF, DOCX) and converts
        them to markdown format while extracting and encoding any embedded images.

        Args:
            file: Uploaded document file to convert

        Returns:
            ConversionOutput: Conversion result with markdown content and images
        """

        pseudonymized_user_id = get_pseudonymized_user_id(current_user, config.hmac_secret)
        logger.info(
            "app_event",
            extra={
                "pseudonym_id": pseudonymized_user_id,
                "event": convert.__name__,
                "file_size": file.size,
            },
        )

        task = asyncio.create_task(document_conversion_service.convert(file))

        while task.done() is False:
            await asyncio.sleep(0.1)
            if await request.is_disconnected():
                task.cancel()
                logger.info("Conversion task cancelled due to client disconnect")
                return ConversionOutput(html="")
        result = task.result()
        return ConversionOutput(html=result.html)

    logger.info("Conversion router configured")
    return router
