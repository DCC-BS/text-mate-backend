from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, final

import httpx
from fastapi import status
from starlette.datastructures import UploadFile

from text_mate_backend.models.conversion_result import ConversionResult
from text_mate_backend.models.docling_response import (
    DoclingDocument,
    DoclingResponse,
    DocumentResponse,
)
from text_mate_backend.models.error_codes import (
    INVALID_MIME_TYPE,
    NO_DOCUMENT,
    UNEXPECTED_ERROR,
)
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger(__name__)


def get_mimetype(path_source: Path) -> str:
    """Get MIME type based on file extension."""

    extension = path_source.suffix.lower()
    mimetypes = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".html": "text/html",
        ".adoc": "text/asciidoc",
        ".md": "text/markdown",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".txt": "text/plain",
    }

    logger.debug(
        f"""Determined MIME type '{mimetypes.get(extension, "invalid")}'
        for extension '{extension}' annd path '{path_source}'"""
    )
    return mimetypes.get(extension, "invalid")


def validate_mimetype(mimetype: str, logger_context: dict[str, Any]) -> None:
    if len(mimetype) == 0:
        logger.error("MIME type is empty", extra=logger_context)

        raise ApiErrorException(
            {
                "errorId": INVALID_MIME_TYPE,
                "status": status.HTTP_400_BAD_REQUEST,
                "debugMessage": "MIME type is empty",
            }
        )

    if mimetype == "invalid":
        logger.error("Invalid MIME type", extra=logger_context)
        raise ApiErrorException(
            {
                "errorId": INVALID_MIME_TYPE,
                "status": status.HTTP_400_BAD_REQUEST,
                "debugMessage": "Invalid MIME type",
            }
        )


def extract_docling_document(response: str, logger_context: dict[str, Any]) -> DocumentResponse:
    docling_response = DoclingResponse.model_validate(response)
    if docling_response.document.json_content is None:
        logger.error(
            "Docling response does not contain a document",
            extra=logger_context,
        )
        raise ApiErrorException(
            {
                "errorId": NO_DOCUMENT,
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "debugMessage": "Document conversion failed the json content is None",
            }
        )

    return docling_response.document


@final
class DocumentConversionService:
    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __del__(self) -> None:
        await self.client.aclose()

    async def fetch_docling_file_convert(
        self,
        files: Mapping[str, tuple[str, BinaryIO | BytesIO, str]],
        options: dict[str, str | list[str] | bool],
    ) -> httpx.Response:
        logger.debug(f"Fetching docling file convert with URL: {self.config.docling_url}/convert/file")
        response = await self.client.post(
            self.config.docling_url + "/convert/file",
            files=files,
            data=options,
        )

        if 200 <= response.status_code < 300:
            return response
        else:
            # For error responses, safely handle potential binary content
            try:
                error_text = response.text
                logger.error(f"Error response: {error_text}")

                raise ApiErrorException(
                    {
                        "errorId": UNEXPECTED_ERROR,
                        "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "debugMessage": "Unexpected error occurred",
                    }
                )
            except UnicodeDecodeError as e:
                logger.exception(f"Error response contains binary data (status: {response.status_code})")
                raise ApiErrorException(
                    {
                        "errorId": UNEXPECTED_ERROR,
                        "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "debugMessage": "Binary data in error response",
                    }
                ) from e

    async def convert_to_docling(
        self,
        file: UploadFile | BytesIO,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> DoclingDocument:
        languages = ["de", "en", "fr", "it"]

        # Handle both UploadFile and BytesIO cases
        if isinstance(file, UploadFile):
            content = file.file.read()
            filename = filename or file.filename or "uploaded_document"
            if content_type is None:
                content_type = get_mimetype(Path(filename))
        else:
            # It's a BytesIO object
            content = file.read()
            filename = filename or "uploaded_document"
            if content_type is None:
                content_type = get_mimetype(Path(filename))

        validate_mimetype(content_type, logger_context={"content_type": content_type})

        files = {"files": (filename, BytesIO(content), content_type)}
        options: dict[str, str | list[str] | bool] = {
            "to_formats": ["json"],
            "image_export_mode": "referenced",
            "do_ocr": True,
            "ocr_engine": "easyocr",
            "ocr_lang": languages,
            "table_mode": "accurate",
            "pdf_backend": "pypdfium2",
        }

        logger_context = {"options": options, "content_type": content_type}

        response = await self.fetch_docling_file_convert(files, options)
        json_response = response.json()

        document = extract_docling_document(json_response, logger_context)

        if document.json_content is None:
            logger.error("Docling response does not contain a document", extra=logger_context)

            raise ApiErrorException(
                {
                    "errorId": NO_DOCUMENT,
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "debugMessage": "Docling response does not contain a document",
                }
            )

        # Ensure we return a DoclingDocument instance
        if isinstance(document.json_content, dict):
            return DoclingDocument.model_validate(document.json_content)
        return document.json_content

    async def convert(
        self,
        file: UploadFile | BytesIO,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> ConversionResult:
        languages = ["de", "en", "fr", "it"]

        logger.debug(f"type of file: {type(file)}")

        # Handle both UploadFile and BytesIO cases
        if isinstance(file, UploadFile):
            content = file.file.read()
            filename = file.filename or "uploaded_document"
            logger.debug(f"Filename from UploadFile: {filename}")
            if content_type is None:
                content_type = get_mimetype(Path(filename))
        else:
            logger.debug("File is not an UploadFile instance")
            # It's a BytesIO object
            content = file.read()
            filename = filename or "uploaded_document"
            if content_type is None:
                content_type = get_mimetype(Path(filename))

        validate_mimetype(content_type, logger_context={"content_type": content_type})

        files = {"files": (filename, BytesIO(content), content_type)}
        options: dict[str, str | list[str] | bool] = {
            "to_formats": ["md", "json"],
            "image_export_mode": "referenced",
            "do_ocr": True,
            "ocr_engine": "easyocr",
            "ocr_lang": languages,
            "table_mode": "accurate",
            "pdf_backend": "pypdfium2",
        }

        response = await self.fetch_docling_file_convert(files, options)
        json_response = response.json()
        docling_response = extract_docling_document(
            json_response, logger_context={"options": options, "content_type": content_type}
        )

        # Extract markdown content from the docling response
        markdown = docling_response.md_content or ""

        return ConversionResult(markdown=markdown)
