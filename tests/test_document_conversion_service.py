import io
import os
from unittest.mock import patch

import httpx
import pytest
from starlette.datastructures import UploadFile

from text_mate_backend.models.error_codes import (
    DOCUMENT_CONVERSION_ERROR,
    DOCUMENT_CONVERSION_TIMEOUT,
    INVALID_MIME_TYPE,
)
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.services.document_conversion_service import DocumentConversionService
from text_mate_backend.utils.configuration import Configuration


def test_error_codes_defined():
    assert DOCUMENT_CONVERSION_ERROR == "document_conversion_error"
    assert DOCUMENT_CONVERSION_TIMEOUT == "document_conversion_timeout"
    assert INVALID_MIME_TYPE == "invalid_mime_type"


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
    assert config.docling_conversion_timeout_seconds == 300.0
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
    assert "Corrupted PDF" in exc_info.value.error_response["debugMessage"]
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
    assert "missing task_id" in exc_info.value.error_response["debugMessage"]
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
    assert "status 500" in exc_info.value.error_response["debugMessage"]
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
    assert "Docling connection error" in exc_info.value.error_response["debugMessage"]
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

