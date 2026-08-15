"""Tests for POST /convert/doc router endpoint.

Covers:
- Successful document conversion
- Error propagation for ApiErrorException (conversion error, timeout, invalid mime type)
- Client disconnect cancellation handling
- Validation errors (missing file)
- Usage tracking logging
"""

import asyncio
import os
from typing import Any, final
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi_azure_auth.user import User
from httpx import ASGITransport, AsyncClient

from text_mate_backend.models.conversion_result import ConversionResult
from text_mate_backend.models.error_codes import (
    DOCUMENT_CONVERSION_ERROR,
    DOCUMENT_CONVERSION_TIMEOUT,
    INVALID_MIME_TYPE,
)
from text_mate_backend.models.error_response import ApiErrorException

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
class StubUsageTracking:
    def __init__(self) -> None:
        self.events: list[tuple[str, str | None, dict[str, Any]]] = []

    def log_event(self, action: str, user_id: str | None, **fields: Any) -> None:
        self.events.append((action, user_id, fields))


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
