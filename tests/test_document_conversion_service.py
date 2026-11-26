import asyncio
import base64
import io
import os
from unittest.mock import patch

import httpx
import pytest
from starlette.datastructures import UploadFile

from text_mate_backend.models.error_codes import (
    DOCUMENT_CONVERSION_ERROR,
    DOCUMENT_CONVERSION_TIMEOUT,
    IMAGE_TOO_LARGE,
    INVALID_MIME_TYPE,
    UNSUPPORTED_IMAGE_FORMAT,
)
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.services.document_conversion_service import DocumentConversionService, image_dimensions
from text_mate_backend.utils.configuration import Configuration


def test_error_codes_defined():
    assert DOCUMENT_CONVERSION_ERROR == "document_conversion_error"
    assert DOCUMENT_CONVERSION_TIMEOUT == "document_conversion_timeout"
    assert INVALID_MIME_TYPE == "invalid_mime_type"
    assert UNSUPPORTED_IMAGE_FORMAT == "unsupported_image_format"
    assert IMAGE_TOO_LARGE == "image_too_large"


def test_configuration_docling_defaults():
    config = Configuration(
        environment="test",
        docling_url="http://localhost:5001/v1",
        docling_api_key="test-key",
        llm_api_key="test-llm-key",
        llm_url="http://localhost:8000/v1",
        llm_model="test-model",
        azure_client_id="test-client-id",
        azure_tenant_id="test-tenant-id",
        azure_frontend_client_id="test-frontend-client-id",
        hmac_secret="test-hmac-secret",
    )
    assert config.docling_poll_interval_seconds == 1.0
    assert config.docling_conversion_timeout_seconds == 480.0
    assert config.docling_http_timeout_seconds == 30.0


def test_configuration_from_env():
    env_vars = {
        "AUTH_MODE": "none",
        "APP_MODE": "dev",
        "CLIENT_URL": "http://localhost:3000",
        "LLM_API_KEY": "test-key",
        "LLM_URL": "http://localhost:8000/v1",
        "LLM_MODEL": "test-model",
        "DOCLING_URL": "http://localhost:5001/v1",
        "DOCLING_API_KEY": "test-docling-key",
        "DOCLING_POLL_INTERVAL_SECONDS": "2.5",
        "DOCLING_CONVERSION_TIMEOUT_SECONDS": "120.0",
        "DOCLING_HTTP_TIMEOUT_SECONDS": "15.0",
        "LLM_HEALTH_CHECK_URL": "http://localhost:8001/health",
        "AZURE_SCOPE_DESCRIPTION": "user_impersonation",
        "HMAC_SECRET": "secret",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        config = Configuration.from_env()
        assert config.docling_poll_interval_seconds == 2.5
        assert config.docling_conversion_timeout_seconds == 120.0
        assert config.docling_http_timeout_seconds == 15.0


@pytest.fixture
def service_config() -> Configuration:
    return Configuration(
        environment="test",
        docling_url="http://localhost:5001/v1",
        docling_api_key="test-key",
        llm_api_key="test-llm-key",
        llm_url="http://localhost:8000/v1",
        llm_model="test-model",
        azure_client_id="test-client-id",
        azure_tenant_id="test-tenant-id",
        azure_frontend_client_id="test-frontend-client-id",
        hmac_secret="test-hmac-secret",
        docling_poll_interval_seconds=0.01,
        docling_conversion_timeout_seconds=0.05,
        docling_http_timeout_seconds=5.0,
    )


@pytest.mark.anyio
async def test_convert_success_async_polling(service_config: Configuration):
    poll_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        assert request.headers.get("Authorization") == "Bearer test-key"
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(200, json={"task_id": "task-123", "task_status": "pending", "task_type": "convert"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-123":
            poll_count += 1
            if poll_count == 1:
                return httpx.Response(
                    200, json={"task_id": "task-123", "task_status": "pending", "task_type": "convert"}
                )
            return httpx.Response(200, json={"task_id": "task-123", "task_status": "success", "task_type": "convert"})
        elif request.method == "GET" and request.url.path == "/v1/result/task-123":
            return httpx.Response(
                200,
                json={
                    "document": {"html_content": "<p>Converted Text</p>"},
                    "status": "success",
                    "processing_time": 1.2,
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    pdf_bytes = b"%PDF-1.4 dummy content"
    upload = UploadFile(file=io.BytesIO(pdf_bytes), filename="sample.pdf")

    res = await service.convert(upload)
    assert res.html == "<p>Converted Text</p>"
    assert poll_count == 2
    await service.close()


@pytest.mark.anyio
async def test_convert_sends_document_timeout(service_config: Configuration):
    submitted_body = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal submitted_body
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            submitted_body = request.read()
            return httpx.Response(200, json={"task_id": "task-123", "task_status": "pending", "task_type": "convert"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-123":
            return httpx.Response(200, json={"task_id": "task-123", "task_status": "success", "task_type": "convert"})
        elif request.method == "GET" and request.url.path == "/v1/result/task-123":
            return httpx.Response(200, json={"document": {"html_content": "<p>ok</p>"}})
        return httpx.Response(404)

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))
    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 dummy content"), filename="sample.pdf")

    await service.convert(upload)
    assert b'name="document_timeout"\r\n\r\n0.05\r\n' in submitted_body
    await service.close()


@pytest.mark.anyio
async def test_convert_poll_failure(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(200, json={"task_id": "task-err", "task_status": "pending", "task_type": "convert"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-err":
            return httpx.Response(
                200,
                json={
                    "task_id": "task-err",
                    "task_status": "failure",
                    "task_type": "convert",
                    "error_message": "Corrupted PDF",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 corrupt"), filename="corrupt.pdf")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_ERROR
    assert exc_info.value.error_response["status"] == 500
    debug_message = exc_info.value.error_response["debugMessage"]
    assert debug_message is not None
    assert "Corrupted PDF" in debug_message
    await service.close()


@pytest.mark.anyio
async def test_convert_poll_skipped(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(200, json={"task_id": "task-skip", "task_status": "pending", "task_type": "convert"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-skip":
            return httpx.Response(
                200,
                json={
                    "task_id": "task-skip",
                    "task_status": "skipped",
                    "task_type": "convert",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 skip"), filename="skipped.pdf")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_ERROR
    assert exc_info.value.error_response["status"] == 500
    await service.close()


@pytest.mark.anyio
async def test_convert_timeout(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(
                200, json={"task_id": "task-timeout", "task_status": "pending", "task_type": "convert"}
            )
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-timeout":
            return httpx.Response(
                200, json={"task_id": "task-timeout", "task_status": "pending", "task_type": "convert"}
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 long"), filename="long.pdf")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_TIMEOUT
    assert exc_info.value.error_response["status"] == 504
    await service.close()


@pytest.mark.anyio
async def test_convert_invalid_mimetype(service_config: Configuration):
    service = DocumentConversionService(service_config)
    upload = UploadFile(file=io.BytesIO(b"binary"), filename="unknown.xyz")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == INVALID_MIME_TYPE
    assert exc_info.value.error_response["status"] == 400
    await service.close()


@pytest.mark.anyio
async def test_submit_async_task_missing_task_id(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_status": "pending"})

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    with pytest.raises(ApiErrorException) as exc_info:
        await service.submit_async_task(
            files={"files": ("doc.pdf", b"content", "application/pdf")},
            options={},
        )

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_ERROR
    assert exc_info.value.error_response["status"] == 500
    debug_message = exc_info.value.error_response["debugMessage"]
    assert debug_message is not None
    assert "missing task_id" in debug_message
    await service.close()


@pytest.mark.anyio
async def test_request_http_error(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    with pytest.raises(ApiErrorException) as exc_info:
        await service._request("GET", "/status/poll/task-1")

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_ERROR
    assert exc_info.value.error_response["status"] == 500
    debug_message = exc_info.value.error_response["debugMessage"]
    assert debug_message is not None
    assert "status 500" in debug_message
    await service.close()


@pytest.mark.anyio
async def test_request_connection_error(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to connect")

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    with pytest.raises(ApiErrorException) as exc_info:
        await service._request("GET", "/status/poll/task-1")

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_ERROR
    assert exc_info.value.error_response["status"] == 500
    debug_message = exc_info.value.error_response["debugMessage"]
    assert debug_message is not None
    assert "Docling connection error" in debug_message
    await service.close()


@pytest.mark.anyio
async def test_convert_with_bytesio(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(200, json={"task_id": "task-bytesio", "task_status": "pending"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-bytesio":
            return httpx.Response(200, json={"task_id": "task-bytesio", "task_status": "success"})
        elif request.method == "GET" and request.url.path == "/v1/result/task-bytesio":
            return httpx.Response(200, json={"document": {"html_content": "<p>BytesIO Content</p>"}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with DocumentConversionService(service_config, transport=transport) as service:
        bio = io.BytesIO(b"%PDF-1.4 bytesio content")
        res = await service.convert(bio, filename="doc.pdf")
        assert res.html == "<p>BytesIO Content</p>"


@pytest.mark.anyio
async def test_fetch_task_result_none_document(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"document": None, "status": "success"})

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)
    result = await service.fetch_task_result("task-none-doc")
    assert result.html == ""
    await service.close()


@pytest.mark.anyio
async def test_fetch_task_result_document_timeout(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "document": {"html_content": "<p>first pages only</p>"},
                "status": "partial_success",
                "errors": [
                    {
                        "component_type": "pipeline",
                        "module_name": "StandardPdfPipeline",
                        "error_message": "document timeout exceeded",
                        "category": "timeout",
                        "page_no": 66,
                    }
                ],
            },
        )

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))
    with pytest.raises(ApiErrorException) as exc_info:
        await service.fetch_task_result("task-timeout")
    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_TIMEOUT
    assert exc_info.value.error_response["status"] == 504
    await service.close()


@pytest.mark.anyio
async def test_fetch_task_result_partial_success_without_timeout(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "document": {"html_content": "<p>most pages</p>"},
                "status": "partial_success",
                "errors": [{"component_type": "model", "error_message": "page 3 failed", "category": "unknown"}],
            },
        )

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))
    result = await service.fetch_task_result("task-partial")
    assert result.html == "<p>most pages</p>"
    await service.close()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("docling_url", "path", "expected_url"),
    [
        ("http://localhost:5001/v1", "/status/poll/123", "http://localhost:5001/v1/status/poll/123"),
        ("http://localhost:5001/v1/", "/status/poll/123", "http://localhost:5001/v1/status/poll/123"),
        ("http://localhost:5001/v1", "status/poll/123", "http://localhost:5001/v1/status/poll/123"),
        ("http://localhost:5001/v1/", "status/poll/123", "http://localhost:5001/v1/status/poll/123"),
        ("http://localhost:5001///", "///status/poll/123", "http://localhost:5001/status/poll/123"),
    ],
)
async def test_request_url_normalization(service_config: Configuration, docling_url: str, path: str, expected_url: str):
    recorded_url: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal recorded_url
        recorded_url = str(request.url)
        return httpx.Response(200, json={"task_status": "success"})

    service_config_copy = service_config.model_copy(update={"docling_url": docling_url})
    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config_copy, transport=transport)
    await service._request("GET", path)
    assert recorded_url == expected_url
    await service.close()


@pytest.mark.anyio
@pytest.mark.parametrize("ext,content_type", [(".gif", "image/gif"), (".webp", "image/webp"), (".txt", "text/plain")])
async def test_convert_gif_webp_txt_mimetypes_accepted(service_config: Configuration, ext: str, content_type: str):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(200, json={"task_id": "task-mime", "task_status": "pending"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-mime":
            return httpx.Response(200, json={"task_id": "task-mime", "task_status": "success"})
        elif request.method == "GET" and request.url.path == "/v1/result/task-mime":
            return httpx.Response(200, json={"document": {"html_content": "<p>Content</p>"}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)
    upload = UploadFile(file=io.BytesIO(b"file content"), filename=f"sample{ext}")
    res = await service.convert(upload)
    assert res.html == "<p>Content</p>"
    await service.close()


@pytest.mark.anyio
async def test_convert_poll_request_timeout(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(
                200, json={"task_id": "task-req-timeout", "task_status": "pending", "task_type": "convert"}
            )
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-req-timeout":
            raise httpx.ReadTimeout("Request timed out during poll")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 sample"), filename="sample.pdf")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_TIMEOUT
    assert exc_info.value.error_response["status"] == 504
    debug_message = exc_info.value.error_response["debugMessage"]
    assert debug_message is not None
    assert "Docling conversion timed out after" in debug_message
    await service.close()


@pytest.mark.anyio
async def test_convert_poll_transient_error_recovery(service_config: Configuration):
    poll_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(
                200, json={"task_id": "task-recovery", "task_status": "pending", "task_type": "convert"}
            )
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-recovery":
            poll_count += 1
            if poll_count == 1:
                return httpx.Response(500, text="Internal Server Error")
            elif poll_count == 2:
                return httpx.Response(
                    200, json={"task_id": "task-recovery", "task_status": "pending", "task_type": "convert"}
                )
            return httpx.Response(
                200, json={"task_id": "task-recovery", "task_status": "success", "task_type": "convert"}
            )
        elif request.method == "GET" and request.url.path == "/v1/result/task-recovery":
            return httpx.Response(
                200,
                json={
                    "document": {"html_content": "<p>Recovered Content</p>"},
                    "status": "success",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 sample"), filename="sample.pdf")
    res = await service.convert(upload)
    assert res.html == "<p>Recovered Content</p>"
    assert poll_count == 3
    await service.close()


@pytest.mark.anyio
async def test_convert_poll_continuous_error_deadline_timeout(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(
                200, json={"task_id": "task-cont-err", "task_status": "pending", "task_type": "convert"}
            )
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-cont-err":
            return httpx.Response(500, text="Internal Server Error")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 sample"), filename="sample.pdf")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_TIMEOUT
    assert exc_info.value.error_response["status"] == 504
    await service.close()


@pytest.mark.anyio
async def test_convert_cancellation_during_polling(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(200, json={"task_id": "task-cancel", "task_status": "pending"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-cancel":
            return httpx.Response(200, json={"task_id": "task-cancel", "task_status": "pending"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 sample"), filename="sample.pdf")
    task = asyncio.create_task(service.convert(upload))
    await asyncio.sleep(0.02)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    await service.close()


# ── Image upload support ────────────────────────────────────────────────────

# Minimal real 1x1 images of each accepted raster format.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwcJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPDs0NDX/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)
GIF_1X1 = base64.b64decode("R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==")
WEBP_1X1 = base64.b64decode("UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA==")


def _bmp(width: int, height: int) -> bytes:
    """Build a minimal 24-bit uncompressed BMP."""
    pixel_data = b"\x00" * (width * height * 3)
    file_header = (
        b"BM" + (54 + len(pixel_data)).to_bytes(4, "little") + b"\x00\x00\x00\x00" + (54).to_bytes(4, "little")
    )
    dib_header = (
        (40).to_bytes(4, "little")
        + width.to_bytes(4, "little")
        + height.to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (24).to_bytes(2, "little")
        + b"\x00" * 16
    )
    return file_header + dib_header + pixel_data


def _bmp_core(width: int, height: int) -> bytes:
    """Build a minimal BMP with a 12-byte BITMAPCOREHEADER (16-bit width/height)."""
    file_header = b"BM" + (26).to_bytes(4, "little") + b"\x00\x00\x00\x00" + (26).to_bytes(4, "little")
    core_header = (
        (12).to_bytes(4, "little")
        + width.to_bytes(2, "little")
        + height.to_bytes(2, "little")
        + (1).to_bytes(2, "little")  # bcPlanes
        + (24).to_bytes(2, "little")  # bcBitCount
    )
    return file_header + core_header


def _png_header(width: int, height: int) -> bytes:
    """Build a PNG signature + IHDR header (no pixel data) claiming the given size."""
    ihdr_payload = b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x06\x00\x00\x00"
    return b"\x89PNG\r\n\x1a\n" + len(ihdr_payload).to_bytes(4, "big") + ihdr_payload


def _tiff_header(width: int, height: int, big_endian: bool) -> bytes:
    """Build a header-only TIFF with inline SHORT width/height IFD entries."""
    end = "big" if big_endian else "little"

    def u16(v: int) -> bytes:
        return v.to_bytes(2, end)

    def u32(v: int) -> bytes:
        return v.to_bytes(4, end)

    def entry(tag: int, typ: int, count: int, value: bytes) -> bytes:
        return u16(tag) + u16(typ) + u32(count) + value

    ifd = u16(2)  # entry count
    ifd += entry(256, 3, 1, u16(width) + b"\x00\x00")  # ImageWidth, SHORT, left-justified
    ifd += entry(257, 3, 1, u16(height) + b"\x00\x00")  # ImageHeight, SHORT, left-justified
    ifd += u32(0)  # next IFD offset
    magic = b"MM" if big_endian else b"II"
    return magic + u16(42) + u32(8) + ifd  # IFD follows the 8-byte header


def _jpeg_header(width: int, height: int, fill: bytes = b"") -> bytes:
    """Build an SOF0 JPEG header (no pixel data) claiming the given size.

    `fill` inserts 0xFF padding bytes before the SOF marker, as allowed by JPEG.
    """
    sof = (
        b"\xff\xc0"
        + (11).to_bytes(2, "big")
        + b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x01\x01\x11\x00\x03"
    )
    return b"\xff\xd8" + fill + sof


@pytest.mark.anyio
@pytest.mark.parametrize(
    "filename,content,image_bytes",
    [
        ("sample.png", "image/png", PNG_1X1),
        ("sample.jpg", "image/jpeg", JPEG_1X1),
        ("sample.gif", "image/gif", GIF_1X1),
        ("sample.webp", "image/webp", WEBP_1X1),
        ("sample.bmp", "image/bmp", _bmp(2, 2)),
    ],
)
async def test_convert_image_happy_path_returns_html(
    service_config: Configuration, filename: str, content: str, image_bytes: bytes
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(200, json={"task_id": "task-img", "task_status": "pending"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-img":
            return httpx.Response(200, json={"task_id": "task-img", "task_status": "success"})
        elif request.method == "GET" and request.url.path == "/v1/result/task-img":
            return httpx.Response(200, json={"document": {"html_content": "<h1>Scanned text</h1>"}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = DocumentConversionService(service_config, transport=transport)
    upload = UploadFile(file=io.BytesIO(image_bytes), filename=filename)

    result = await service.convert(upload)

    assert result.html == "<h1>Scanned text</h1>"
    assert result.model_dump() == {"html": "<h1>Scanned text</h1>"}
    await service.close()


@pytest.mark.anyio
@pytest.mark.parametrize("filename,mimetype", [("photo.heic", "image/heic"), ("photo.heif", "image/heif")])
async def test_convert_heic_heif_rejected_with_dedicated_error(
    service_config: Configuration, filename: str, mimetype: str
):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP request must be made for unsupported formats")

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))

    # Via filename-derived mimetype ...
    upload = UploadFile(file=io.BytesIO(b"xx"), filename=filename)
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)
    assert exc_info.value.error_response["errorId"] == UNSUPPORTED_IMAGE_FORMAT
    assert exc_info.value.error_response["status"] == 400

    # ... and via explicitly provided content type.
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(io.BytesIO(b"xx"), filename="photo", content_type=mimetype)
    assert exc_info.value.error_response["errorId"] == UNSUPPORTED_IMAGE_FORMAT
    assert exc_info.value.error_response["status"] == 400
    await service.close()


@pytest.mark.anyio
async def test_convert_image_too_large_bytes_rejected(service_config: Configuration):
    limited_config = service_config.model_copy(update={"image_max_bytes": 10})

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP request must be made for oversized images")

    service = DocumentConversionService(limited_config, transport=httpx.MockTransport(handler))
    upload = UploadFile(file=io.BytesIO(PNG_1X1), filename="sample.png")  # 70 bytes > 10

    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == IMAGE_TOO_LARGE
    assert exc_info.value.error_response["status"] == 413
    await service.close()


@pytest.mark.anyio
async def test_convert_image_too_many_pixels_rejected(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP request must be made for oversized images")

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))
    # Header-only PNG claiming 6000x6000 = 36 MP > 25 MP limit.
    upload = UploadFile(file=io.BytesIO(_png_header(6000, 6000)), filename="huge.png")

    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == IMAGE_TOO_LARGE
    assert exc_info.value.error_response["status"] == 413
    debug_message = exc_info.value.error_response["debugMessage"]
    assert debug_message is not None
    assert "6000x6000" in debug_message
    await service.close()


@pytest.mark.anyio
async def test_convert_image_at_pixel_limit_accepted(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/convert/file/async":
            return httpx.Response(200, json={"task_id": "task-limit", "task_status": "pending"})
        elif request.method == "GET" and request.url.path == "/v1/status/poll/task-limit":
            return httpx.Response(200, json={"task_id": "task-limit", "task_status": "success"})
        elif request.method == "GET" and request.url.path == "/v1/result/task-limit":
            return httpx.Response(200, json={"document": {"html_content": "<p>ok</p>"}})
        return httpx.Response(404)

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))
    # 5000x5000 = exactly 25_000_000 pixels, at but not over the limit.
    upload = UploadFile(file=io.BytesIO(_png_header(5000, 5000)), filename="border.png")

    result = await service.convert(upload)
    assert result.html == "<p>ok</p>"
    await service.close()


@pytest.mark.parametrize(
    "content,content_type,expected",
    [
        (PNG_1X1, "image/png", (1, 1)),
        (JPEG_1X1, "image/jpeg", (1, 1)),
        (GIF_1X1, "image/gif", (1, 1)),
        (WEBP_1X1, "image/webp", (1, 1)),
        (_bmp(3, 5), "image/bmp", (3, 5)),
        (_bmp_core(3, 5), "image/bmp", (3, 5)),
        (_bmp_core(6000, 6000), "image/bmp", (6000, 6000)),
        (_tiff_header(7, 9, big_endian=False), "image/tiff", (7, 9)),
        (_tiff_header(7, 9, big_endian=True), "image/tiff", (7, 9)),
        (_jpeg_header(7, 9, fill=b"\xff" * 4), "image/jpeg", (7, 9)),
        (b"\xff\xd8\xff\xff", "image/jpeg", None),  # only fill bytes after SOI
        (b"", "image/png", None),
        (b"\x89PNG\r\n\x1a\nshort", "image/png", None),
        (b"not an image", "image/jpeg", None),
    ],
)
def test_image_dimensions(content: bytes, content_type: str, expected: tuple[int, int] | None):
    assert image_dimensions(content, content_type) == expected


@pytest.mark.anyio
async def test_convert_oversized_jpeg_with_fill_bytes_rejected(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP request must be made for oversized images")

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))
    # Header-only JPEG with 0xFF fill bytes before the SOF marker claiming 6000x6000
    # = 36 MP > 25 MP limit; well below the 10 MB byte limit.
    upload = UploadFile(file=io.BytesIO(_jpeg_header(6000, 6000, fill=b"\xff" * 4)), filename="padded.jpg")

    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == IMAGE_TOO_LARGE
    assert exc_info.value.error_response["status"] == 413
    await service.close()


@pytest.mark.anyio
async def test_convert_oversized_bmp_core_header_rejected(service_config: Configuration):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP request must be made for oversized images")

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))
    # BITMAPCOREHEADER (16-bit fields) claiming 6000x6000 = 36 MP > 25 MP limit;
    # well below the 10 MB byte limit.
    upload = UploadFile(file=io.BytesIO(_bmp_core(6000, 6000)), filename="old.bmp")

    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == IMAGE_TOO_LARGE
    assert exc_info.value.error_response["status"] == 413
    await service.close()


@pytest.mark.anyio
@pytest.mark.parametrize("big_endian", [False, True], ids=["little", "big"])
async def test_convert_oversized_tiff_rejected_both_byte_orders(service_config: Configuration, big_endian: bool):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP request must be made for oversized images")

    service = DocumentConversionService(service_config, transport=httpx.MockTransport(handler))
    # Header-only TIFF with inline SHORT dims claiming 6000x6000 = 36 MP > 25 MP
    # limit; well below the 10 MB byte limit.
    upload = UploadFile(file=io.BytesIO(_tiff_header(6000, 6000, big_endian=big_endian)), filename="scan.tiff")

    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == IMAGE_TOO_LARGE
    assert exc_info.value.error_response["status"] == 413
    await service.close()
