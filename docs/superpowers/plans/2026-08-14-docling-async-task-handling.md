# Docling Asynchronous Task Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition backend Docling document conversion from synchronous HTTP request to asynchronous task submission with status polling, update conversion parameters, update docling Docker image, and provide localized frontend error messages.

**Architecture:** `DocumentConversionService` submits document files to Docling-serve's `/v1/convert/file/async` endpoint, polls `/v1/status/poll/{task_id}` until completion or timeout, and fetches converted HTML from `/v1/result/{task_id}`. Structured error codes (`document_conversion_error`, `document_conversion_timeout`, `invalid_mime_type`) are propagated to the frontend and displayed with localized i18n messages.

**Tech Stack:** Python 3.13, FastAPI, httpx, pytest, pytest-asyncio/anyio, Nuxt/Vue 4 i18n.

## Global Constraints
- Target container image: `ghcr.io/dcc-bs/dcc-docling-serve-cu130:1.30.0`
- PDF backend: `docling_parse`
- OCR parameter: `ocr_preset: "rapidocr"` (not deprecated `ocr_engine: "easyocr"`)
- Default polling interval: `1.0` second
- Default conversion timeout: `300.0` seconds (5 minutes)
- Default HTTP call timeout: `30.0` seconds
- Error codes: `invalid_mime_type`, `document_conversion_error`, `document_conversion_timeout`, `unexpected_error`

---

### Task 1: Configuration, Docker Compose, & Error Codes

**Files:**
- Modify: `src/text_mate_backend/models/error_codes.py`
- Modify: `src/text_mate_backend/utils/configuration.py:10-85`
- Modify: `docker-compose.yml:39-58`
- Test: `tests/test_document_conversion_service.py`

**Interfaces:**
- Produces:
  - `DOCUMENT_CONVERSION_ERROR = "document_conversion_error"` in `error_codes.py`
  - `DOCUMENT_CONVERSION_TIMEOUT = "document_conversion_timeout"` in `error_codes.py`
  - `Configuration.docling_poll_interval_seconds: float`
  - `Configuration.docling_conversion_timeout_seconds: float`
  - `Configuration.docling_http_timeout_seconds: float`

- [ ] **Step 1: Write failing test for new configuration fields and error codes**

Create `tests/test_document_conversion_service.py`:
```python
from text_mate_backend.models.error_codes import (
    DOCUMENT_CONVERSION_ERROR,
    DOCUMENT_CONVERSION_TIMEOUT,
    INVALID_MIME_TYPE,
)
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
    )
    assert config.docling_poll_interval_seconds == 1.0
    assert config.docling_conversion_timeout_seconds == 300.0
    assert config.docling_http_timeout_seconds == 30.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_document_conversion_service.py -v`
Expected: FAIL (missing imports / attributes on Configuration)

- [ ] **Step 3: Implement Configuration fields, error codes, and docker-compose image**

In `src/text_mate_backend/models/error_codes.py`:
```python
UNEXPECTED_ERROR = "unexpected_error"
NO_DOCUMENT = "no_document"
CHECK_TEXT_ERROR = "check_text_error"
REWRITE_TEXT_ERROR = "rewrite_text_error"
INVALID_MIME_TYPE = "invalid_mime_type"
LOADING_FILES_ERROR = "loading_files_error"
TEXT_ANALYSIS_ERROR = "text_analysis_error"
FIX_TEXT_ERROR = "fix_text_error"
DOCUMENT_CONVERSION_ERROR = "document_conversion_error"
DOCUMENT_CONVERSION_TIMEOUT = "document_conversion_timeout"
```

In `src/text_mate_backend/utils/configuration.py`:
```python
    docling_url: str = Field(description="The URL for Docling service", default="http://localhost:5001/v1")
    docling_api_key: str = Field(
        description="The API key for Docling service",
        default="none",
    )
    docling_poll_interval_seconds: float = Field(
        description="Interval in seconds between Docling task status polling requests",
        default=1.0,
    )
    docling_conversion_timeout_seconds: float = Field(
        description="Maximum seconds to wait for Docling conversion task to complete",
        default=300.0,
    )
    docling_http_timeout_seconds: float = Field(
        description="Per-request HTTP timeout in seconds for Docling API calls",
        default=30.0,
    )
```
Update `Configuration.from_env()` in `src/text_mate_backend/utils/configuration.py`:
```python
docling_poll_interval_seconds = (float(os.getenv("DOCLING_POLL_INTERVAL_SECONDS", "1.0")),)
docling_conversion_timeout_seconds = (float(os.getenv("DOCLING_CONVERSION_TIMEOUT_SECONDS", "300.0")),)
docling_http_timeout_seconds = (float(os.getenv("DOCLING_HTTP_TIMEOUT_SECONDS", "30.0")),)
```

In `docker-compose.yml`:
Change line 40:
```yaml
    docling-serve:
        image: ghcr.io/dcc-bs/dcc-docling-serve-cu130:1.30.0
        container_name: docling-serve-text-mate
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_document_conversion_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/text_mate_backend/models/error_codes.py src/text_mate_backend/utils/configuration.py docker-compose.yml tests/test_document_conversion_service.py
git commit -m "feat(docling): update error codes, config parameters, and docling docker image"
```

---

### Task 2: Implement Async Task Handling in `DocumentConversionService`

**Files:**
- Modify: `src/text_mate_backend/services/document_conversion_service.py`
- Test: `tests/test_document_conversion_service.py`

**Interfaces:**
- Consumes: `Configuration`, `error_codes`, `ApiErrorException`
- Produces: `DocumentConversionService.convert(file, filename, content_type) -> ConversionResult`

- [ ] **Step 1: Write unit tests for async task conversion flows**

Add test cases to `tests/test_document_conversion_service.py`:
```python
import io
import pytest
import httpx
from starlette.datastructures import UploadFile
from text_mate_backend.models.error_codes import (
    DOCUMENT_CONVERSION_ERROR,
    DOCUMENT_CONVERSION_TIMEOUT,
    INVALID_MIME_TYPE,
)
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.services.document_conversion_service import DocumentConversionService
from text_mate_backend.utils.configuration import Configuration


@pytest.fixture
def service_config():
    return Configuration(
        environment="test",
        docling_url="http://localhost:5001/v1",
        docling_api_key="test-key",
        llm_api_key="test-llm-key",
        llm_url="http://localhost:8000/v1",
        llm_model="test-model",
        docling_poll_interval_seconds=0.01,
        docling_conversion_timeout_seconds=0.1,
        docling_http_timeout_seconds=5.0,
    )


@pytest.mark.anyio
async def test_convert_success_async_polling(service_config, respx_mock):
    service = DocumentConversionService(service_config)

    # 1. Async submit
    submit_route = respx_mock.post("http://localhost:5001/v1/convert/file/async").respond(
        status_code=200,
        json={"task_id": "task-123", "task_status": "pending", "task_type": "convert"},
    )
    # 2. Status poll 1: pending
    # 3. Status poll 2: success
    poll_route = respx_mock.get("http://localhost:5001/v1/status/poll/task-123")
    poll_route.side_effect = [
        httpx.Response(200, json={"task_id": "task-123", "task_status": "pending", "task_type": "convert"}),
        httpx.Response(200, json={"task_id": "task-123", "task_status": "success", "task_type": "convert"}),
    ]
    # 4. Result fetch
    result_route = respx_mock.get("http://localhost:5001/v1/result/task-123").respond(
        status_code=200,
        json={"document": {"html_content": "<p>Converted Text</p>"}, "status": "success", "processing_time": 1.2},
    )

    pdf_bytes = b"%PDF-1.4 dummy content"
    upload = UploadFile(file=io.BytesIO(pdf_bytes), filename="sample.pdf")

    res = await service.convert(upload)
    assert res.html == "<p>Converted Text</p>"
    assert submit_route.called
    assert poll_route.call_count == 2
    assert result_route.called
    await service.close()


@pytest.mark.anyio
async def test_convert_poll_failure(service_config, respx_mock):
    service = DocumentConversionService(service_config)

    respx_mock.post("http://localhost:5001/v1/convert/file/async").respond(
        status_code=200,
        json={"task_id": "task-err", "task_status": "pending", "task_type": "convert"},
    )
    respx_mock.get("http://localhost:5001/v1/status/poll/task-err").respond(
        status_code=200,
        json={
            "task_id": "task-err",
            "task_status": "failure",
            "task_type": "convert",
            "error_message": "Corrupted PDF",
        },
    )

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 corrupt"), filename="corrupt.pdf")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_ERROR
    assert exc_info.value.error_response["status"] == 500
    await service.close()


@pytest.mark.anyio
async def test_convert_timeout(service_config, respx_mock):
    service = DocumentConversionService(service_config)

    respx_mock.post("http://localhost:5001/v1/convert/file/async").respond(
        status_code=200,
        json={"task_id": "task-timeout", "task_status": "pending", "task_type": "convert"},
    )
    # Always return pending to trigger timeout
    respx_mock.get("http://localhost:5001/v1/status/poll/task-timeout").respond(
        status_code=200,
        json={"task_id": "task-timeout", "task_status": "pending", "task_type": "convert"},
    )

    upload = UploadFile(file=io.BytesIO(b"%PDF-1.4 long"), filename="long.pdf")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == DOCUMENT_CONVERSION_TIMEOUT
    assert exc_info.value.error_response["status"] == 504
    await service.close()


@pytest.mark.anyio
async def test_convert_invalid_mimetype(service_config):
    service = DocumentConversionService(service_config)
    upload = UploadFile(file=io.BytesIO(b"binary"), filename="unknown.xyz")
    with pytest.raises(ApiErrorException) as exc_info:
        await service.convert(upload)

    assert exc_info.value.error_response["errorId"] == INVALID_MIME_TYPE
    assert exc_info.value.error_response["status"] == 400
    await service.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_document_conversion_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Clean Async Task Polling in `DocumentConversionService`**

Update `src/text_mate_backend/services/document_conversion_service.py`:
```python
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

# [Keep existing get_mimetype and validate_mimetype functions]


@final
class DocumentConversionService:
    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=self.config.docling_http_timeout_seconds)

    async def __aenter__(self) -> "DocumentConversionService":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        await self.client.aclose()

    # [Keep existing _prepare_file_data helper]

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_document_conversion_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/text_mate_backend/services/document_conversion_service.py tests/test_document_conversion_service.py
git commit -m "feat(docling): implement async task submission, polling, and result retrieval"
```

---

### Task 3: Router Integration and Route Tests

**Files:**
- Modify: `src/text_mate_backend/routers/convert_route.py`
- Test: `tests/test_convert_router.py`

**Interfaces:**
- Consumes: `DocumentConversionService`
- Produces: `POST /convert/doc` route

- [ ] **Step 1: Write tests for `convert_route`**

Create `tests/test_convert_router.py`:
```python
import io
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from text_mate_backend.models.conversion_result import ConversionResult
from text_mate_backend.routers.convert_route import create_router
from text_mate_backend.utils.auth import AuthSchema


@pytest.mark.anyio
async def test_convert_route_success():
    app = FastAPI()
    mock_service = AsyncMock()
    mock_service.convert.return_value = ConversionResult(html="<p>Test</p>")

    mock_usage = AsyncMock()
    mock_auth = AsyncMock()

    app.include_router(
        create_router(
            document_conversion_service=mock_service,
            auth_scheme=mock_auth,
            usage_tracking_service=mock_usage,
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")}
        response = await ac.post("/convert/doc", files=files)

    assert response.status_code == 200
    assert response.json() == {"html": "<p>Test</p>"}
    assert mock_service.convert.called
```

- [ ] **Step 2: Run test to verify it runs and passes**

Run: `uv run pytest tests/test_convert_router.py -v`
Expected: PASS

- [ ] **Step 3: Commit router tests**

```bash
git add tests/test_convert_router.py
git commit -m "test(convert): add router tests for document conversion"
```

---

### Task 4: Frontend Error Handling & Localization Updates

**Files:**
- Modify: `/home/yanick/code/textmate/text-mate-frontend/app/composables/useFileConvert.ts`
- Modify: `/home/yanick/code/textmate/text-mate-frontend/i18n/locales/de.json`
- Modify: `/home/yanick/code/textmate/text-mate-frontend/i18n/locales/en.json`

**Interfaces:**
- Consumes: Backend HTTP errors with `errorId` (`document_conversion_error`, `document_conversion_timeout`, `invalid_mime_type`)
- Produces: Localized error toasts and messages in UI

- [ ] **Step 1: Add error translations to `de.json` and `en.json`**

In `text-mate-frontend/i18n/locales/de.json`:
Under `"errors"`:
```json
        "invalid_mime_type": "Ungültiges oder nicht unterstütztes Dateiformat.",
        "document_conversion_error": "Fehler bei der Dokumentenkonvertierung. Bitte überprüfen Sie die Datei und versuchen Sie es erneut.",
        "document_conversion_timeout": "Die Dokumentenkonvertierung hat das Zeitlimit überschritten. Bitte versuchen Sie es mit einer kleineren Datei erneut."
```

In `text-mate-frontend/i18n/locales/en.json`:
Under `"errors"`:
```json
        "invalid_mime_type": "Invalid or unsupported file format.",
        "document_conversion_error": "Failed to convert document. Please check the file and try again.",
        "document_conversion_timeout": "Document conversion timed out. Please try again with a smaller file."
```

- [ ] **Step 2: Update `useFileConvert.ts` to extract `errorId` and display localized error**

In `text-mate-frontend/app/composables/useFileConvert.ts`:
Update the `catch (err)` block:
```typescript
        } catch (err: unknown) {
            let errorId: string | undefined;
            if (err instanceof FetchError && err.data && typeof err.data === "object") {
                errorId = err.data.errorId;
            }

            const localizedErrorMessage = errorId && te(`errors.${errorId}`)
                ? t(`errors.${errorId}`)
                : t("upload.errorDescription");

            error.value = localizedErrorMessage;
            logger.error(err, "File conversion error:", { errorId });
            useUseErrorDialog().sendError(localizedErrorMessage);
        }
```

- [ ] **Step 3: Verify frontend typecheck or tests if available**

Run biome / typecheck in `text-mate-frontend`.

- [ ] **Step 4: Commit frontend changes**

```bash
git -C /home/yanick/code/textmate/text-mate-frontend add app/composables/useFileConvert.ts i18n/locales/de.json i18n/locales/en.json
git -C /home/yanick/code/textmate/text-mate-frontend commit -m "feat(upload): display localized backend conversion error messages"
```

---

### Task 5: Full Regression Verification

**Files:**
- Verify all tests across backend and lint checks.

- [ ] **Step 1: Run full backend pytest test suite**

Run: `uv run pytest`
Expected: All 435+ tests pass (100%).

- [ ] **Step 2: Run linter and formatting checks**

Run: `uv run ruff check .`
Expected: Clean with 0 errors.

- [ ] **Step 3: Run final commit if needed**
