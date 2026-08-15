import os
from typing import Any, cast

from dcc_backend_common.fastapi_error_handling import inject_api_error_handler
from dcc_backend_common.usage_tracking import UsageTrackingService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_azure_auth.user import User

from text_mate_backend.models.error_codes import REWRITE_TEXT_ERROR
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


class StubUsageTracking:
    def log_event(self, action: str, user_id: str | None, **fields: Any) -> None:
        pass


def no_auth() -> User | None:
    return None


def test_quick_action_retired_plain_language_returns_400():
    from text_mate_backend.routers.quick_action import create_router
    from text_mate_backend.services.actions.quick_action_service import QuickActionService

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
    service = QuickActionService(user_action_service=cast(Any, None), config=config)

    app = FastAPI()
    inject_api_error_handler(app)
    app.include_router(
        create_router(
            quick_action_service=service,
            auth_scheme=no_auth,
            usage_tracking_service=cast(UsageTrackingService, StubUsageTracking()),
        )
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/quick-action", json={"action": "plain_language", "text": "Ein schwerer Text."})
    assert response.status_code == 400
    data = response.json()
    assert data["errorId"] == REWRITE_TEXT_ERROR
    assert "retired" in data["debugMessage"]
