from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, final

import httpx
from fastapi import status
from starlette.datastructures import UploadFile

from text_mate_backend.models.conversion_result import ConversionResult
from text_mate_backend.models.docling_response import (
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
        for extension '{extension}' and path '{path_source}'"""
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


@final
class DocumentConversionService:
    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        """Explicitly close the HTTP client. Should be called when done with the service."""
        await self.client.aclose()

    def _prepare_file_data(
        self,
        file: UploadFile | BytesIO,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> tuple[bytes, str, str]:
        """
        Extract common file handling logic for document conversion.

        Args:
            file: UploadFile or BytesIO object containing the document
            filename: Optional filename override
            content_type: Optional content type override

        Returns:
            Tuple of (content, filename, content_type)
        """
        # Handle both UploadFile and BytesIO cases
        if isinstance(file, UploadFile):
            # Seek to start for UploadFile
            _ = file.file.seek(0)
            content = file.file.read()
            # Resolve filename: prefer provided, then UploadFile.filename, then default
            resolved_filename = filename or file.filename or "uploaded_document"
        else:
            # It's a BytesIO object
            _ = file.seek(0)
            content = file.read()
            # Resolve filename: prefer provided, then default
            resolved_filename = filename or "uploaded_document"

        # Determine content_type if missing
        if content_type is None:
            content_type = get_mimetype(Path(resolved_filename))

        # Validate the mimetype
        validate_mimetype(content_type, logger_context={"content_type": content_type})

        return content, resolved_filename, content_type

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

    async def convert(
        self,
        file: UploadFile | BytesIO,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> ConversionResult:
        languages = ["de", "en", "fr", "it"]

        logger.debug(f"type of file: {type(file)}")

        # Prepare file data using common helper
        content, filename, content_type = self._prepare_file_data(file, filename, content_type)
        logger.debug(f"Resolved filename: {filename}")

        files = {"files": (filename, BytesIO(content), content_type)}
        options: dict[str, str | list[str] | bool] = {
            "to_formats": ["html"],
            "image_export_mode": "placeholder",
            "do_ocr": True,
            "ocr_engine": "easyocr",
            "ocr_lang": languages,
            "table_mode": "accurate",
            "pdf_backend": "pypdfium2",
        }

        response = await self.fetch_docling_file_convert(files, options)
        json_response = response.json()
        html = json_response.get("document", {}).get("html_content", "")
        return ConversionResult(html=html)
