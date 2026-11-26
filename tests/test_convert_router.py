"""Tests for POST /convert/doc router endpoint.

Covers:
- Successful document conversion
- Error propagation for ApiErrorException (conversion error, timeout, invalid mime type)
- Client disconnect cancellation handling
- Validation errors (missing file)
- Usage tracking logging
"""

import asyncio
import base64
import os
from typing import Any, final
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from dcc_backend_common.fastapi_error_handling import inject_api_error_handler
from dcc_backend_common.usage_tracking import UsageTrackingService
from fastapi import FastAPI
from fastapi_azure_auth.user import User
from httpx import ASGITransport, AsyncClient

from text_mate_backend.models.conversion_result import ConversionResult
from text_mate_backend.models.error_codes import (
    DOCUMENT_CONVERSION_ERROR,
    DOCUMENT_CONVERSION_TIMEOUT,
    IMAGE_TOO_LARGE,
    INVALID_MIME_TYPE,
    UNSUPPORTED_IMAGE_FORMAT,
)
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.services.document_conversion_service import DocumentConversionService
from text_mate_backend.utils.configuration import Configuration

TEST_ENV = {
    "AUTH_MODE": "none",
    "APP_MODE": "dev",
    "CLIENT_URL": "http://localhost:3000",
    "LLM_API_KEY": "test",
    "LLM_URL": "http://localhost:8001/v1",
    "LLM_MODEL": "test-model",
    "DOCLING_URL": "http://localhost:5001/v1",
    "DOCLING_API_KEY": "none",
    "LLM_HEALTH_CHECK_URL": "http://localhost:8001/health",
    "HMAC_SECRET": "test-secret",
}
for _key, _value in TEST_ENV.items():
    os.environ.setdefault(_key, _value)


@final
class StubUsageTracking(UsageTrackingService):
    def __init__(self) -> None:
        super().__init__(hmac_secret="test-secret")
        self.events: list[tuple[str | None, str | None, dict[str, Any]]] = []

    def log_event(
        self,
        action: str | None = None,
        user_id: str | None = None,
        *,
        module: str | None = None,
        func: str | None = None,
        **kwargs: str | int | float | bool | None,
    ) -> None:
        self.events.append((action, user_id, dict(kwargs)))


def no_auth() -> User | None:
    return None


def build_app(
    mock_service: AsyncMock,
    usage: StubUsageTracking | None = None,
) -> FastAPI:
    # Imported here, not at module scope, so TEST_ENV is in place before the
    # container is constructed as a side effect of the import.
    from text_mate_backend.routers.convert_route import create_router

    app = FastAPI()
    app.include_router(
        create_router(
            document_conversion_service=mock_service,
            auth_scheme=no_auth,
            usage_tracking_service=usage or StubUsageTracking(),
        )
    )
    return app


@pytest.mark.anyio
async def test_convert_route_success():
    mock_service = AsyncMock()
    mock_service.convert.return_value = ConversionResult(html="<p>Converted document content</p>")
    usage = StubUsageTracking()
    app = build_app(mock_service, usage)

    file_content = b"%PDF-1.4 dummy document content"
    files = {"file": ("sample.pdf", file_content, "application/pdf")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/convert/doc", files=files)

    assert response.status_code == 200
    assert response.json() == {"html": "<p>Converted document content</p>"}
    assert mock_service.convert.called

    assert len(usage.events) == 1
    action, user_id, fields = usage.events[0]
    assert action == "document.convert"
    assert user_id is None
    assert fields["file_size"] == len(file_content)
    assert fields["content_type"] == "application/pdf"


@pytest.mark.anyio
async def test_convert_route_error_propagation_conversion_error():
    mock_service = AsyncMock()
    mock_service.convert.side_effect = ApiErrorException(
        {
            "errorId": DOCUMENT_CONVERSION_ERROR,
            "status": 500,
            "debugMessage": "Docling request failed with status 500",
        }
    )
    app = build_app(mock_service)

    files = {"file": ("sample.pdf", b"%PDF-1.4 dummy", "application/pdf")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with pytest.raises(ApiErrorException) as exc_info:
            await ac.post("/convert/doc", files=files)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_ERROR
    assert exc_info.value.error_response["status"] == 500
    assert exc_info.value.error_response["debugMessage"] == "Docling request failed with status 500"


@pytest.mark.anyio
async def test_convert_route_error_propagation_timeout():
    mock_service = AsyncMock()
    mock_service.convert.side_effect = ApiErrorException(
        {
            "errorId": DOCUMENT_CONVERSION_TIMEOUT,
            "status": 504,
            "debugMessage": "Docling conversion timed out after 300.0s",
        }
    )
    app = build_app(mock_service)

    files = {"file": ("large.pdf", b"%PDF-1.4 dummy", "application/pdf")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with pytest.raises(ApiErrorException) as exc_info:
            await ac.post("/convert/doc", files=files)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_TIMEOUT
    assert exc_info.value.error_response["status"] == 504


@pytest.mark.anyio
async def test_convert_route_error_propagation_invalid_mimetype():
    mock_service = AsyncMock()
    mock_service.convert.side_effect = ApiErrorException(
        {
            "errorId": INVALID_MIME_TYPE,
            "status": 400,
            "debugMessage": "Unsupported file format: text/plain",
        }
    )
    app = build_app(mock_service)

    files = {"file": ("unsupported.txt", b"plain text", "text/plain")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with pytest.raises(ApiErrorException) as exc_info:
            await ac.post("/convert/doc", files=files)

    assert exc_info.value.error_response["errorId"] == INVALID_MIME_TYPE
    assert exc_info.value.error_response["status"] == 400


@pytest.mark.anyio
async def test_convert_route_client_disconnect_cancellation():
    task_was_cancelled = False

    async def long_convert(file):
        nonlocal task_was_cancelled
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            task_was_cancelled = True
            raise
        return ConversionResult(html="<p>Completed</p>")

    mock_service = AsyncMock()
    mock_service.convert = long_convert
    app = build_app(mock_service)

    files = {"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")}

    with patch("fastapi.Request.is_disconnected", new_callable=AsyncMock) as mock_disconnect:
        mock_disconnect.return_value = True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/convert/doc", files=files)

    # Allow cancellation to propagate in event loop
    await asyncio.sleep(0.01)

    assert response.status_code == 200
    assert response.json() == {"html": ""}
    assert task_was_cancelled is True


@pytest.mark.anyio
async def test_convert_route_missing_file_validation_error():
    mock_service = AsyncMock()
    app = build_app(mock_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/convert/doc")

    assert response.status_code == 422
    assert not mock_service.convert.called


# ── Image uploads ───────────────────────────────────────────────────────────

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.mark.anyio
async def test_convert_route_accepts_image_upload():
    mock_service = AsyncMock()
    mock_service.convert.return_value = ConversionResult(html="<p>OCR text from photo</p>")
    usage = StubUsageTracking()
    app = build_app(mock_service, usage)

    files = {"file": ("handwritten.png", PNG_1X1, "image/png")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/convert/doc", files=files)

    assert response.status_code == 200
    assert response.json() == {"html": "<p>OCR text from photo</p>"}
    assert mock_service.convert.called

    _, _, fields = usage.events[0]
    assert fields["content_type"] == "image/png"
    assert fields["file_size"] == len(PNG_1X1)


SERVICE_TEST_CONFIG_KWARGS = {
    "environment": "test",
    "docling_url": "http://localhost:5001/v1",
    "docling_api_key": "test-key",
    "llm_api_key": "test-llm-key",
    "llm_url": "http://localhost:8000/v1",
    "llm_model": "test-model",
    "azure_client_id": "test-client-id",
    "azure_tenant_id": "test-tenant-id",
    "azure_frontend_client_id": "test-frontend-client-id",
    "hmac_secret": "test-hmac-secret",
}


def build_app_with_real_service(config: Configuration) -> FastAPI:
    """Build the router around a real DocumentConversionService so the image
    guards run for real, with production error handling wired in."""

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP request must leave the service during guard rejection")

    # Imported here, not at module scope, so TEST_ENV is in place before the
    # container is constructed as a side effect of the import.
    from text_mate_backend.routers.convert_route import create_router

    app = FastAPI()
    inject_api_error_handler(app)
    service = DocumentConversionService(config, transport=httpx.MockTransport(unreachable))
    app.include_router(
        create_router(
            document_conversion_service=service,
            auth_scheme=no_auth,
            usage_tracking_service=StubUsageTracking(),
        )
    )
    return app


@pytest.mark.anyio
async def test_convert_route_heic_returns_400_with_error_id():
    app = build_app_with_real_service(Configuration(**SERVICE_TEST_CONFIG_KWARGS))

    files = {"file": ("photo.heic", b"heic-bytes", "image/heic")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/convert/doc", files=files)

    assert response.status_code == 400
    body = response.json()
    assert body["errorId"] == UNSUPPORTED_IMAGE_FORMAT
    assert "image/heic" in body["debugMessage"]


@pytest.mark.anyio
async def test_convert_route_oversized_image_returns_413():
    config = Configuration(**{**SERVICE_TEST_CONFIG_KWARGS, "image_max_bytes": 10})
    app = build_app_with_real_service(config)

    files = {"file": ("big.png", PNG_1X1, "image/png")}  # 70 bytes > 10 byte limit

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/convert/doc", files=files)

    assert response.status_code == 413
    body = response.json()
    assert body["errorId"] == IMAGE_TOO_LARGE
