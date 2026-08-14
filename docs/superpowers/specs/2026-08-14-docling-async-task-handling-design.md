# Design Spec: Docling Asynchronous Task Handling & Error Propagation

**Date:** 2026-08-14  
**Author:** AI Pair Programmer / Antigravity  
**Status:** In Review  

---

## 1. Overview & Objectives

TextMate's backend document conversion currently invokes `docling-serve` synchronously via `POST /v1/convert/file`. For large or complex PDF and Office files, long conversion times frequently cause HTTP client or gateway timeouts.

This project transitions the document conversion handling to an asynchronous task pattern:
1. Submit conversion task asynchronously via `POST /v1/convert/file/async`.
2. Poll task status periodically via `GET /v1/status/poll/{task_id}` until completion or timeout.
3. Retrieve conversion output via `GET /v1/result/{task_id}`.
4. Update conversion parameters (`pdf_backend: "docling_parse"`, `ocr_preset: "rapidocr"`).
5. Update the `docling-serve` Docker container to `ghcr.io/dcc-bs/dcc-docling-serve-cu130:1.30.0`.
6. Standardize structured error codes and messages across backend and frontend with localized German (`de.json`) and English (`en.json`) translations.

---

## 2. Docling Container & Parameter Updates

### 2.1 Docker Compose
Update `docker-compose.yml` for `docling-serve`:
- **Image:** `ghcr.io/dcc-bs/dcc-docling-serve-cu130:1.30.0` (replacing `ghcr.io/docling-project/docling-serve-cu130:main`)

### 2.2 Conversion Payload Options
In `DocumentConversionService.convert()`:
```python
options: dict[str, Any] = {
    "to_formats": ["html"],
    "image_export_mode": "placeholder",
    "do_ocr": True,
    "ocr_preset": "rapidocr",
    "ocr_lang": ["de", "en", "fr", "it"],
    "table_mode": "accurate",
    "pdf_backend": "docling_parse",
}
```
- Replaces deprecated `ocr_engine: "easyocr"` with modern `ocr_preset: "rapidocr"`.
- Replaces `pdf_backend: "pypdfium2"` with `pdf_backend: "docling_parse"`.

---

## 3. Configuration Parameters

Add configurable parameters to `Configuration` in `src/text_mate_backend/utils/configuration.py`:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DOCLING_POLL_INTERVAL_SECONDS` | `float` | `1.0` | Polling frequency between status checks |
| `DOCLING_CONVERSION_TIMEOUT_SECONDS` | `float` | `300.0` | Maximum total time allowed for a conversion task before timing out |
| `DOCLING_HTTP_TIMEOUT_SECONDS` | `float` | `30.0` | Per-request timeout for HTTP network calls (submit, poll, result) |

---

## 4. Architecture & Asynchronous Workflow

```
FastAPI Client              DocumentConversionService                     Docling-Serve (/v1)
     |                                 |                                           |
     |--- POST /convert/doc ---------->|                                           |
     |                                 |--- POST /convert/file/async ------------->|
     |                                 |<-- 200 {task_id, task_status: "pending"} -|
     |                                 |                                           |
     |                                 |   [Loop while status == pending/started]  |
     |                                 |--- GET /status/poll/{task_id} ----------->|
     |                                 |<-- 200 {task_status: "started"} ----------|
     |                                 |   [await asyncio.sleep(poll_interval)]    |
     |                                 |--- GET /status/poll/{task_id} ----------->|
     |                                 |<-- 200 {task_status: "success"} ----------|
     |                                 |                                           |
     |                                 |--- GET /result/{task_id} ---------------->|
     |                                 |<-- 200 {document: {html_content: "..."}} -|
     |                                 |                                           |
     |<-- 200 ConversionResult(html) --|                                           |
```

### 4.1 Component Design

All HTTP calls are routed through a single helper `_request(method, path, **kwargs)` that handles headers, URL building, logging, and error conversion.

1. **Unified Request Helper (`_request`)**:
   - Sends HTTP requests with `Authorization: Bearer <docling_api_key>`.
   - Calls `response.raise_for_status()`.
   - Converts any `httpx.HTTPStatusError` or `httpx.RequestError` into `ApiErrorException(DOCUMENT_CONVERSION_ERROR)`.

2. **Submission (`submit_async_task`)**:
   - Calls `_request("POST", "/convert/file/async", files=files, data=options)`.
   - Returns `task_id`.

3. **Status Polling Loop (`poll_task_status`)**:
   - Simple `while True` loop:
     - Checks elapsed time; if `elapsed > timeout`, raises `ApiErrorException(DOCUMENT_CONVERSION_TIMEOUT)`.
     - Calls `_request("GET", f"/status/poll/{task_id}")`.
     - If `task_status` in `("success", "partial_success")`: returns.
     - If `task_status` in `("failure", "skipped")`: raises `ApiErrorException(DOCUMENT_CONVERSION_ERROR)`.
     - `await asyncio.sleep(poll_interval)`.

4. **Result Fetching (`fetch_task_result`)**:
   - Calls `_request("GET", f"/result/{task_id}")`.
   - Returns `ConversionResult(html=...)`.

5. **Orchestrator (`convert`)**:
   - Prepares file -> submits task -> polls until completion -> returns result.

---

## 5. Error Handling & Frontend Propagation

### 5.1 Backend Error Codes
In `src/text_mate_backend/models/error_codes.py`:
- `INVALID_MIME_TYPE = "invalid_mime_type"` (HTTP 400)
- `DOCUMENT_CONVERSION_ERROR = "document_conversion_error"` (HTTP 500)
- `DOCUMENT_CONVERSION_TIMEOUT = "document_conversion_timeout"` (HTTP 504)
- `UNEXPECTED_ERROR = "unexpected_error"` (HTTP 500)

### 5.2 Frontend Error Handling
In `text-mate-frontend/app/composables/useFileConvert.ts`:
- Catch `FetchError` and extract `err.data?.errorId`.
- Look up localized message `t('errors.' + errorId)`. If not present, fall back to `t('upload.errorDescription')`.
- Trigger toast / error dialog via `useUseErrorDialog().sendError(...)`.

### 5.3 Frontend Localizations
Add corresponding error messages to i18n dictionaries:

**German (`text-mate-frontend/i18n/locales/de.json`):**
```json
{
  "errors": {
    "invalid_mime_type": "Ungültiges oder nicht unterstütztes Dateiformat.",
    "document_conversion_error": "Fehler bei der Dokumentenkonvertierung. Bitte überprüfen Sie die Datei und versuchen Sie es erneut.",
    "document_conversion_timeout": "Die Dokumentenkonvertierung hat das Zeitlimit überschritten. Bitte versuchen Sie es mit einer kleineren Datei erneut."
  }
}
```

**English (`text-mate-frontend/i18n/locales/en.json`):**
```json
{
  "errors": {
    "invalid_mime_type": "Invalid or unsupported file format.",
    "document_conversion_error": "Failed to convert document. Please check the file and try again.",
    "document_conversion_timeout": "Document conversion timed out. Please try again with a smaller file."
  }
}
```

---

## 6. Testing Strategy

1. **Unit Tests for `DocumentConversionService` (`tests/test_document_conversion_service.py`)**:
   - `test_convert_success`: Mocks async task creation (`/convert/file/async`), polling (`/status/poll/{task_id}`: `pending` -> `success`), and result fetching (`/result/{task_id}`).
   - `test_convert_poll_failure`: Mocks task status transition to `failure` and verifies `ApiErrorException` with `DOCUMENT_CONVERSION_ERROR`.
   - `test_convert_timeout`: Mocks repeated `pending` status exceeding timeout and verifies `ApiErrorException` with `DOCUMENT_CONVERSION_TIMEOUT`.
   - `test_invalid_mimetype`: Verifies `ApiErrorException` with `INVALID_MIME_TYPE` without calling external service.
   - `test_polling_retry_transient_http_error`: Verifies that a transient HTTP error during status polling recovers when the subsequent poll succeeds.
2. **Router Tests (`tests/test_convert_router.py`)**:
   - Verifies `POST /convert/doc` endpoint handling and cancellation on client disconnect.
3. **Full Regression Suite**:
   - Run `uv run pytest` to ensure all 435+ existing tests continue to pass.
