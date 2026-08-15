"""Tests for advisor router endpoints: POST /advisor/validate, POST /advisor/fix, GET /advisor/docs."""

import json
import os
from collections.abc import AsyncIterator, Sequence
from typing import Any, cast, final

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_azure_auth.user import User

from text_mate_backend.models.rule_models import (
    RuleDocumentDescription,
    RulesValidationContainer,
    ViolationRange,
    ViolationResult,
)

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


@final
class StubAdvisorService:
    def __init__(self, containers: Sequence[RulesValidationContainer]) -> None:
        self.containers = list(containers)
        self.calls: list[tuple[str, set[str]]] = []

    async def check_text_stream(self, text: str, docs: set[str]) -> AsyncIterator[RulesValidationContainer]:
        self.calls.append((text, docs))
        for container in self.containers:
            yield container

    def get_docs(self, user: User | None) -> list[RuleDocumentDescription]:
        return [
            RuleDocumentDescription(
                id="bundeskanzlei",
                name="Bundeskanzlei",
                files=["doc.pdf"],
                description="Leitfaden",
                version="1.0",
                access=["all"],
            )
        ]

    def can_access_document(self, document_name: str, user: User | None) -> bool:
        return True


@final
class StubFixService:
    def __init__(self, chunks: Sequence[str]) -> None:
        self.chunks = list(chunks)

    async def fix_text_stream(self, text: str, threads: list[Any]) -> AsyncIterator[str]:
        for chunk in self.chunks:
            yield chunk


def no_auth() -> User | None:
    return None


def build_client(
    advisor_service: StubAdvisorService,
    fix_service: StubFixService | None = None,
    usage: StubUsageTracking | None = None,
    **kwargs: Any,
) -> TestClient:
    from text_mate_backend.routers.advisor import create_router

    app = FastAPI()
    app.include_router(
        create_router(
            advisor_service=cast(Any, advisor_service),
            fix_service=cast(Any, fix_service or StubFixService([])),
            auth_scheme=no_auth,
            usage_tracking_service=cast(Any, usage or StubUsageTracking()),
        )
    )
    return TestClient(app, **kwargs)


def parse_lines(body: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


class TestAdvisorValidateRouter:
    def test_validate_wire_format_streams_json_lines(self) -> None:
        containers = [
            RulesValidationContainer(violations=[], checked=0, total=10),
            RulesValidationContainer(
                violations=[
                    ViolationResult(
                        rule_name="Passiv vermeiden",
                        reason="Passiv ist unpersoenlich",
                        proposal="Aktiv formulieren",
                        source="wird gemacht",
                        file_name="doc.pdf",
                        page_number=1,
                        range=ViolationRange(start=0, end=12),
                        collection="bundeskanzlei",
                    )
                ],
                checked=10,
                total=10,
            ),
        ]
        usage = StubUsageTracking()
        advisor_service = StubAdvisorService(containers)

        with build_client(advisor_service, usage=usage) as client:
            response = client.post(
                "/advisor/validate",
                json={"text": "wird gemacht heute.", "docs": ["bundeskanzlei"]},
            )

        assert response.status_code == 200
        assert "application/x-ndjson" in response.headers.get("content-type", "")
        lines = parse_lines(response.text)
        assert len(lines) == 2
        assert lines[0]["checked"] == 0
        assert lines[0]["total"] == 10
        assert lines[0]["violations"] == []
        assert lines[1]["checked"] == 10
        assert len(lines[1]["violations"]) == 1
        assert lines[1]["violations"][0]["rule_name"] == "Passiv vermeiden"
        assert advisor_service.calls == [("wird gemacht heute.", {"bundeskanzlei"})]
        assert len(usage.events) == 1
        assert usage.events[0][0] == "advisor.validate"
