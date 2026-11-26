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
    IMAGE_TOO_LARGE,
    INVALID_MIME_TYPE,
    UNSUPPORTED_IMAGE_FORMAT,
)
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("document_conversion_service")


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
        ".heic": "image/heic",
        ".heif": "image/heif",
        ".txt": "text/plain",
    }

    logger.debug(
        "Determined MIME type",
        mime_type=mimetypes.get(extension, "invalid"),
        extension=extension,
        path=str(path_source),
    )
    return mimetypes.get(extension, "invalid")


def validate_mimetype(mimetype: str, logger_context: Mapping[str, Any]) -> None:
    if len(mimetype) == 0:
        logger.error("MIME type is empty", **logger_context)
        raise ApiErrorException(
            {
                "errorId": INVALID_MIME_TYPE,
                "status": status.HTTP_400_BAD_REQUEST,
                "debugMessage": "MIME type is empty",
            }
        )

    # Explicit rejection with a dedicated errorId: docling cannot decode HEIC/HEIF
    # (iOS shares photos as HEIC by default), so callers get an actionable error
    # instead of a conversion failure.
    if mimetype in ("image/heic", "image/heif"):
        logger.error("Unsupported image format", **logger_context)
        raise ApiErrorException(
            {
                "errorId": UNSUPPORTED_IMAGE_FORMAT,
                "status": status.HTTP_400_BAD_REQUEST,
                "debugMessage": (
                    f"Unsupported image format: {mimetype}. Convert the image to JPEG, PNG or WebP and try again."
                ),
            }
        )

    if mimetype not in [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/html",
        "text/asciidoc",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "text/plain",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
        "image/gif",
        "image/webp",
    ]:
        logger.error("Invalid MIME type", **logger_context)
        raise ApiErrorException(
            {
                "errorId": INVALID_MIME_TYPE,
                "status": status.HTTP_400_BAD_REQUEST,
                "debugMessage": f"Invalid MIME type: {mimetype}",
            }
        )


# Image MIME types accepted for conversion. JPEG, PNG, TIFF, BMP, GIF and WebP are
# ingested natively by docling; HEIC/HEIF are rejected above.
IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/tiff", "image/bmp", "image/gif", "image/webp"}
)


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    # IHDR is always the first chunk: width at 16..20, height at 20..24 (big-endian).
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            return None
        # Skip consecutive 0xFF fill bytes before the marker byte (allowed padding).
        j = i + 1
        while j < len(data) and data[j] == 0xFF:
            j += 1
        if j >= len(data):
            return None
        i = j - 1  # normalize: data[i] is the last fill byte, data[i + 1] the marker
        marker = data[i + 1]
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            # Standalone markers without a length field.
            i += 2
            continue
        if i + 9 > len(data):
            return None
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            # SOF segment: precision at i+4, height at i+5..7, width at i+7..9 (big-endian).
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return width, height
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    return None


def _gif_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 10 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    # Logical screen descriptor: width at 6..8, height at 8..10 (little-endian).
    return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")


def _bmp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 26 or data[:2] != b"BM":
        return None
    dib_size = int.from_bytes(data[14:18], "little")
    if dib_size == 12:
        # BITMAPCOREHEADER: width/height are 16-bit unsigned at 18..20 / 20..22.
        width = int.from_bytes(data[18:20], "little")
        height = int.from_bytes(data[20:22], "little")
    else:
        # INFO/V2+ headers: width/height are 32-bit signed; negative height = top-down.
        width = int.from_bytes(data[18:22], "little", signed=True)
        height = abs(int.from_bytes(data[22:26], "little", signed=True))
    if width <= 0 or height <= 0:
        return None
    return width, height


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8 ":  # lossy
        if data[23:26] != b"\x9d\x01\x2a":
            return None
        # Frame header: width at 26..28, height at 28..30 (14-bit little-endian).
        return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
    if chunk == b"VP8L":  # lossless
        if data[20] != 0x2F:
            return None
        # 14-bit width-1 followed by 14-bit height-1, packed into 32 bits.
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":  # extended file
        # Canvas size: width-1 at 24..27, height-1 at 27..30 (24-bit little-endian).
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    return None


def _tiff_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 8 or data[:2] not in (b"II", b"MM"):
        return None
    byteorder = "little" if data[:2] == b"II" else "big"
    if int.from_bytes(data[2:4], byteorder) != 42:
        return None
    ifd_offset = int.from_bytes(data[4:8], byteorder)
    if len(data) < ifd_offset + 2:
        return None
    entry_count = int.from_bytes(data[ifd_offset : ifd_offset + 2], byteorder)
    width: int | None = None
    height: int | None = None
    for n in range(entry_count):
        start = ifd_offset + 2 + 12 * n
        entry = data[start : start + 12]
        if len(entry) < 12:
            return None
        tag = int.from_bytes(entry[0:2], byteorder)
        field_type = int.from_bytes(entry[2:4], byteorder)
        if field_type == 3:  # SHORT: value is left-justified in the first 2 bytes of the value field
            raw = entry[8:10]
        elif field_type == 4:  # LONG: value fills all 4 bytes
            raw = entry[8:12]
        else:
            continue
        value = int.from_bytes(raw, byteorder)
        if tag == 256:
            width = value
        elif tag == 257:
            height = value
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return width, height


_DIMENSION_PARSERS: Mapping[str, Any] = {
    "image/png": _png_dimensions,
    "image/jpeg": _jpeg_dimensions,
    "image/gif": _gif_dimensions,
    "image/bmp": _bmp_dimensions,
    "image/webp": _webp_dimensions,
    "image/tiff": _tiff_dimensions,
}


def image_dimensions(content: bytes, content_type: str) -> tuple[int, int] | None:
    """Read image width/height from the file header without decoding the image.

    Returns None when the header cannot be parsed (e.g. truncated or corrupt data);
    conversion then proceeds and docling surfaces its own conversion error.
    """
    parser = _DIMENSION_PARSERS.get(content_type)
    if parser is None:
        return None
    try:
        return parser(content)
    except (IndexError, ValueError):
        logger.warning("Could not parse image dimensions", content_type=content_type)
        return None


@final
class DocumentConversionService:
    def __init__(self, config: Configuration, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.docling_http_timeout_seconds, transport=transport)

    async def __aenter__(self) -> "DocumentConversionService":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.client.aclose()

    async def aclose(self) -> None:
        await self.client.aclose()

    async def close(self) -> None:
        await self.client.aclose()

    async def _prepare_file_data(
        self,
        file: UploadFile | BytesIO,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> tuple[bytes, str, str]:
        """Extract common file handling logic for document conversion.

        Args:
            file: UploadFile or BytesIO object containing the document.
            filename: Optional filename override.
            content_type: Optional content type override.

        Returns:
            Tuple of (content_bytes, filename, content_type).
        """
        if isinstance(file, UploadFile):
            await file.seek(0)
            content = await file.read()
            resolved_filename = filename or file.filename or "uploaded_document"
        else:
            file_obj = file
            _ = file_obj.seek(0)
            content = file_obj.read()
            resolved_filename = filename or "uploaded_document"

        if content_type is None:
            content_type = get_mimetype(Path(resolved_filename))

        validate_mimetype(content_type, logger_context={"content_type": content_type})

        if content_type in IMAGE_MIME_TYPES:
            self._validate_image_size(content, content_type)

        return content, resolved_filename, content_type

    def _validate_image_size(self, content: bytes, content_type: str) -> None:
        """Reject images over the configured byte and pixel limits with a 413."""
        if len(content) > self.config.image_max_bytes:
            logger.error(
                "Image exceeds maximum file size",
                content_type=content_type,
                size=len(content),
                max_bytes=self.config.image_max_bytes,
            )
            raise ApiErrorException(
                {
                    "errorId": IMAGE_TOO_LARGE,
                    "status": status.HTTP_413_CONTENT_TOO_LARGE,
                    "debugMessage": f"Image exceeds maximum size of {self.config.image_max_bytes} bytes",
                }
            )

        dimensions = image_dimensions(content, content_type)
        if dimensions is not None:
            width, height = dimensions
            pixels = width * height
            if pixels > self.config.image_max_pixels:
                logger.error(
                    "Image exceeds maximum pixel count",
                    content_type=content_type,
                    width=width,
                    height=height,
                    pixels=pixels,
                    max_pixels=self.config.image_max_pixels,
                )
                raise ApiErrorException(
                    {
                        "errorId": IMAGE_TOO_LARGE,
                        "status": status.HTTP_413_CONTENT_TOO_LARGE,
                        "debugMessage": (
                            f"Image of {width}x{height} pixels exceeds maximum of {self.config.image_max_pixels} pixels"
                        ),
                    }
                )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.config.docling_url.rstrip('/')}/{path.lstrip('/')}"
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
        except httpx.TimeoutException:
            raise
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
        retry_backoff = self.config.docling_poll_interval_seconds
        max_backoff = max(self.config.docling_poll_interval_seconds, 10.0)

        while True:
            elapsed = time.monotonic() - start_time
            remaining = self.config.docling_conversion_timeout_seconds - elapsed
            if remaining <= 0:
                logger.error("Docling task conversion timed out", task_id=task_id, elapsed=elapsed)
                raise ApiErrorException(
                    {
                        "errorId": DOCUMENT_CONVERSION_TIMEOUT,
                        "status": status.HTTP_504_GATEWAY_TIMEOUT,
                        "debugMessage": f"Docling conversion timed out after {elapsed:.1f}s",
                    }
                )

            try:
                response = await self._request("GET", f"/status/poll/{task_id}", timeout=remaining)
            except httpx.TimeoutException as e:
                elapsed = time.monotonic() - start_time
                logger.error("Docling task conversion timed out", task_id=task_id, elapsed=elapsed)
                raise ApiErrorException(
                    {
                        "errorId": DOCUMENT_CONVERSION_TIMEOUT,
                        "status": status.HTTP_504_GATEWAY_TIMEOUT,
                        "debugMessage": f"Docling conversion timed out after {elapsed:.1f}s",
                    }
                ) from e
            except ApiErrorException as e:
                if e.error_response.get("errorId") != DOCUMENT_CONVERSION_ERROR:
                    raise
                logger.warning(
                    "Docling polling request encountered transient error, retrying",
                    task_id=task_id,
                    error=e.error_response.get("debugMessage"),
                )
                sleep_duration = min(
                    retry_backoff,
                    max(0.0, self.config.docling_conversion_timeout_seconds - (time.monotonic() - start_time)),
                )
                await asyncio.sleep(sleep_duration)
                retry_backoff = min(retry_backoff * 2, max_backoff)
                continue

            retry_backoff = self.config.docling_poll_interval_seconds
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
        # A conversion cut off by document_timeout is a partial_success missing its last pages
        if any(error.get("category") == "timeout" for error in json_response.get("errors") or []):
            logger.error("Docling conversion hit its document timeout", task_id=task_id)
            raise ApiErrorException(
                {
                    "errorId": DOCUMENT_CONVERSION_TIMEOUT,
                    "status": status.HTTP_504_GATEWAY_TIMEOUT,
                    "debugMessage": "Docling stopped the conversion at its document timeout",
                }
            )
        html = (json_response.get("document") or {}).get("html_content", "")
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
            "md_compact_tables": True,
            # Docling stops the conversion on the worker after this many seconds. Docling starts
            # counting only when the worker picks the task up, after we started polling, so we give
            # up first and the worker stops soon after instead of converting for nobody.
            "document_timeout": self.config.docling_conversion_timeout_seconds,
        }

        task_id = await self.submit_async_task(files, options)
        await self.poll_task_status(task_id)
        return await self.fetch_task_result(task_id)
