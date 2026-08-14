import asyncio
import time
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any, final

import httpx
from dcc_backend_common.logger import get_logger
from fastapi import status
from starlette.datastructures import UploadFile

from text_mate_backend.models.conversion_result import ConversionResult
from text_mate_backend.models.error_codes import (
    DOCUMENT_CONVERSION_ERROR,
    DOCUMENT_CONVERSION_TIMEOUT,
    INVALID_MIME_TYPE,
)
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.utils.configuration import Configuration

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
        "Determined MIME type",
        mime_type=mimetypes.get(extension, "invalid"),
        extension=extension,
        path=str(path_source),
    )
    return mimetypes.get(extension, "invalid")


def validate_mimetype(mimetype: str, logger_context: dict[str, Any]) -> None:
    if len(mimetype) == 0:
        logger.error("MIME type is empty", **logger_context)

        raise ApiErrorException(
            {
                "errorId": INVALID_MIME_TYPE,
                "status": status.HTTP_400_BAD_REQUEST,
                "debugMessage": "MIME type is empty",
            }
        )

    if mimetype == "invalid":
        logger.error("Invalid MIME type", **logger_context)
        raise ApiErrorException(
            {
                "errorId": INVALID_MIME_TYPE,
                "status": status.HTTP_400_BAD_REQUEST,
                "debugMessage": "Invalid MIME type",
            }
        )


@final
class DocumentConversionService:
    def __init__(self, config: Configuration, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=self.config.docling_http_timeout_seconds, transport=transport)

    async def __aenter__(self) -> "DocumentConversionService":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Explicitly close the HTTP client. Should be called when done with the service."""
        await self.client.aclose()

    async def _prepare_file_data(
        self,
        file: UploadFile | BytesIO,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> tuple[bytes, str, str]:
        """
        Extract common file handling logic for document conversion.

        Uses asynchronous I/O for `UploadFile` to avoid blocking the event loop,
        while keeping a single in-memory copy of the content (bytes) and
        avoiding the previous extra `BytesIO` wrapper.

        Args:
            file: UploadFile or BytesIO object containing the document
            filename: Optional filename override
            content_type: Optional content type override

        Returns:
            Tuple of (content_bytes, filename, content_type)
        """
        # Handle both UploadFile and BytesIO cases
        if isinstance(file, UploadFile):
            # Ensure we start reading from the beginning of the stream
            await file.seek(0)
            content = await file.read()
            # Resolve filename: prefer provided, then UploadFile.filename, then default
            resolved_filename = filename or file.filename or "uploaded_document"
        else:
            # It's a BytesIO (or compatible) object; synchronous read is fine (in-memory)
            file_obj = file
            _ = file_obj.seek(0)
            content = file_obj.read()
            # Resolve filename: prefer provided, then default
            resolved_filename = filename or "uploaded_document"

        # Determine content_type if missing
        if content_type is None:
            content_type = get_mimetype(Path(resolved_filename))

        # Validate the mimetype
        validate_mimetype(content_type, logger_context={"content_type": content_type})

        return content, resolved_filename, content_type

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.config.docling_url}{path}"
        headers = {"Authorization": f"Bearer {self.config.docling_api_key}", **kwargs.pop("headers", {})}
        try:
            response = await self.client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error("Docling API HTTP error", url=url, status_code=e.response.status_code, body=e.response.text)
            raise ApiErrorException(
                {
                    "errorId": DOCUMENT_CONVERSION_ERROR,
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "debugMessage": f"Docling request failed with status {e.response.status_code}",
                }
            ) from e
        except httpx.RequestError as e:
            logger.error("Docling connection error", url=url, error=str(e))
            raise ApiErrorException(
                {
                    "errorId": DOCUMENT_CONVERSION_ERROR,
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "debugMessage": f"Docling connection error: {str(e)}",
                }
            ) from e

    async def submit_async_task(
        self,
        files: Mapping[str, tuple[str, bytes, str]],
        options: dict[str, Any],
    ) -> str:
        logger.debug("Submitting docling async file convert task")
        response = await self._request("POST", "/convert/file/async", files=files, data=options)
        task_id = response.json().get("task_id")
        if not task_id:
            logger.error("Docling response missing task_id")
            raise ApiErrorException(
                {
                    "errorId": DOCUMENT_CONVERSION_ERROR,
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "debugMessage": "Docling response missing task_id",
                }
            )
        return str(task_id)

    async def poll_task_status(self, task_id: str) -> None:
        logger.debug("Starting docling task polling", task_id=task_id)
        start_time = time.monotonic()

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed > self.config.docling_conversion_timeout_seconds:
                logger.error("Docling task conversion timed out", task_id=task_id, elapsed=elapsed)
                raise ApiErrorException(
                    {
                        "errorId": DOCUMENT_CONVERSION_TIMEOUT,
                        "status": status.HTTP_504_GATEWAY_TIMEOUT,
                        "debugMessage": f"Docling conversion timed out after {elapsed:.1f}s",
                    }
                )

            response = await self._request("GET", f"/status/poll/{task_id}")
            poll_data = response.json()
            task_status = poll_data.get("task_status")
            logger.debug("Polled docling task status", task_id=task_id, task_status=task_status)

            if task_status in ("success", "partial_success"):
                return
            if task_status in ("failure", "skipped"):
                error_msg = poll_data.get("error_message") or "Conversion task failed"
                logger.error("Docling task failed", task_id=task_id, task_status=task_status, error=error_msg)
                raise ApiErrorException(
                    {
                        "errorId": DOCUMENT_CONVERSION_ERROR,
                        "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "debugMessage": f"Docling task failed: {error_msg}",
                    }
                )

            await asyncio.sleep(self.config.docling_poll_interval_seconds)

    async def fetch_task_result(self, task_id: str) -> ConversionResult:
        logger.debug("Fetching docling task result", task_id=task_id)
        response = await self._request("GET", f"/result/{task_id}")
        json_response = response.json()
        html = json_response.get("document", {}).get("html_content", "")
        return ConversionResult(html=html)

    async def convert(
        self,
        file: UploadFile | BytesIO,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> ConversionResult:
        languages = ["de", "en", "fr", "it"]
        logger.debug("Received file for conversion", file_type=type(file).__name__)

        content, filename, content_type = await self._prepare_file_data(
            file,
            filename,
            content_type,
        )
        logger.debug("Resolved filename", filename=filename)

        files = {"files": (filename, content, content_type)}
        options: dict[str, Any] = {
            "to_formats": ["html"],
            "image_export_mode": "placeholder",
            "do_ocr": True,
            "ocr_preset": "rapidocr",
            "ocr_lang": languages,
            "table_mode": "accurate",
            "pdf_backend": "docling_parse",
        }

        task_id = await self.submit_async_task(files, options)
        await self.poll_task_status(task_id)
        return await self.fetch_task_result(task_id)
