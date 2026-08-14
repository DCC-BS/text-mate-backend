"""Tests for ``POST /simplify`` — the JSON Lines wire contract of section 4.7.

The route is built directly with stub collaborators instead of through the DI
container, so no LLM, no ZIX and no Azure configuration are involved. What is under
test is the contract the frontend parser depends on: one JSON object per line, a
terminal ``done``, unbuffered streaming headers, and a usage event that records the
detected *and* the hinted language so their disagreement can be measured.
"""

import json
import os
from collections.abc import AsyncIterator, Sequence
from typing import Any, cast, final

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_azure_auth.user import User

from text_mate_backend.models.simplify_models import (
    SimplifyDoneEvent,
    SimplifyEvent,
    SimplifyProgressEvent,
    SimplifyStartEvent,
)

SOURCE = "Die Verfuegung ist bis zum 30. Juni 2025 anfechtbar."

#: ``routers/simplify`` imports ``container``, which calls ``Configuration.from_env()``
#: at class-definition time — importing the module is enough to require a full
#: environment. The route under test never reads any of these values (its
#: collaborators are stubs), so placeholders are enough; ``setdefault`` leaves a real
#: developer ``.env`` alone.
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
class StubSimplifyService:
    """Emits a fixed event sequence and records what the route asked it for."""

    def __init__(self, events: Sequence[SimplifyEvent], detected: str | None = "de") -> None:
        self.events = list(events)
        self.detected = detected
        self.calls: list[tuple[str, str | None]] = []
        self.raise_after: int | None = None

    def detect(self, text: str, language_hint: str | None = None) -> tuple[str | None, str | None]:
        return self.detected, self.detected

    async def simplify_stream(self, text: str, language_hint: str | None = None) -> AsyncIterator[SimplifyEvent]:
        self.calls.append((text, language_hint))
        for index, event in enumerate(self.events):
            if self.raise_after is not None and index == self.raise_after:
                raise RuntimeError("the loop exploded")
            yield event


def no_auth() -> User | None:
    return None


def build_client(service: StubSimplifyService, usage: StubUsageTracking, **kwargs: Any) -> TestClient:
    # Imported here, not at module scope, so TEST_ENV is in place before the
    # container is constructed as a side effect of the import.
    from text_mate_backend.routers.simplify import create_router

    app = FastAPI()
    app.include_router(
        create_router(
            simplify_service=cast(Any, service),
            auth_scheme=no_auth,
            usage_tracking_service=cast(Any, usage),
        )
    )
    return TestClient(app, **kwargs)


def default_events() -> list[SimplifyEvent]:
    return [
        SimplifyStartEvent(
            language="de",
            score_label="ZIX",
            scored=True,
            mode="whole",
            units=3,
            score_before=-3.8,
            band_before="hard",
            cefr_before="C1",
        ),
        SimplifyProgressEvent(attempt=1, stage="readability", score=-1.2, band="ok", cefr="B2", units_in_target=2),
        SimplifyProgressEvent(attempt=2, stage="readability", score=0.4, band="easy", cefr="B1", units_in_target=3),
        SimplifyDoneEvent(
            text="Sie koennen die Verfuegung anfechten.",
            language="de",
            score_label="ZIX",
            scored=True,
            score_before=-3.8,
            score_after=1.4,
            band_after="easy",
            cefr_after="A2",
            converged=True,
            unconverged_units=[7, 9],
        ),
    ]


def parse_lines(body: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


class TestWireFormat:
    def test_every_line_is_one_json_event_and_done_is_last(self) -> None:
        service = StubSimplifyService(default_events())
        with build_client(service, StubUsageTracking()) as client:
            response = client.post("/simplify", json={"text": SOURCE, "language": "de"})

        assert response.status_code == 200
        events = parse_lines(response.text)
        assert [event["event"] for event in events] == ["start", "progress", "progress", "done"]
        assert events[-1]["text"] == "Sie koennen die Verfuegung anfechten."
        assert events[-1]["unconverged_units"] == [7, 9]

    def test_start_event_carries_the_section_4_7_fields(self) -> None:
        service = StubSimplifyService(default_events())
        with build_client(service, StubUsageTracking()) as client:
            response = client.post("/simplify", json={"text": SOURCE})

        start = parse_lines(response.text)[0]
        assert start == {
            "event": "start",
            "language": "de",
            "score_label": "ZIX",
            "scored": True,
            "mode": "whole",
            "units": 3,
            "score_before": -3.8,
            "band_before": "hard",
            "cefr_before": "C1",
        }

    def test_response_is_ndjson_and_never_buffered(self) -> None:
        service = StubSimplifyService(default_events())
        with build_client(service, StubUsageTracking()) as client:
            response = client.post("/simplify", json={"text": SOURCE})

        # Without this header nginx holds the progress events until the run finishes,
        # which defeats streaming a loop that can take minutes.
        assert response.headers["x-accel-buffering"] == "no"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["content-type"].startswith("application/x-ndjson")

    def test_non_ascii_is_not_escaped_away(self) -> None:
        events: list[SimplifyEvent] = [
            SimplifyDoneEvent(text="Die Verfügung können Sie anfechten.", language="de", scored=False)
        ]
        service = StubSimplifyService(events)
        with build_client(service, StubUsageTracking()) as client:
            response = client.post("/simplify", json={"text": SOURCE})

        assert parse_lines(response.text)[0]["text"] == "Die Verfügung können Sie anfechten."

    def test_the_language_hint_is_forwarded_to_the_service(self) -> None:
        service = StubSimplifyService(default_events())
        with build_client(service, StubUsageTracking()) as client:
            client.post("/simplify", json={"text": SOURCE, "language": "fr"})

        assert service.calls == [(SOURCE, "fr")]

    def test_the_hint_is_optional(self) -> None:
        service = StubSimplifyService(default_events())
        with build_client(service, StubUsageTracking()) as client:
            response = client.post("/simplify", json={"text": SOURCE})

        assert response.status_code == 200
        assert service.calls == [(SOURCE, None)]

    def test_a_missing_text_is_a_422(self) -> None:
        with build_client(StubSimplifyService([]), StubUsageTracking()) as client:
            assert client.post("/simplify", json={"language": "de"}).status_code == 422


class TestUsageTracking:
    def test_both_languages_are_recorded_so_disagreement_is_measurable(self) -> None:
        usage = StubUsageTracking()
        service = StubSimplifyService(default_events(), detected="de")
        with build_client(service, usage) as client:
            client.post("/simplify", json={"text": SOURCE, "language": "fr"})

        assert len(usage.events) == 1
        action, _user, fields = usage.events[0]
        assert action == "text.simplify"
        assert fields["detected_language"] == "de"
        assert fields["hinted_language"] == "fr"
        assert fields["language_mismatch"] is True
        assert fields["text_length"] == len(SOURCE)

    def test_agreement_is_recorded_as_such(self) -> None:
        usage = StubUsageTracking()
        service = StubSimplifyService(default_events(), detected="de")
        with build_client(service, usage) as client:
            client.post("/simplify", json={"text": SOURCE, "language": "de"})

        assert usage.events[0][2]["language_mismatch"] is False


class TestFailureMidStream:
    def test_a_crash_still_ends_the_stream_with_a_done_carrying_the_original(self) -> None:
        service = StubSimplifyService(default_events())
        service.raise_after = 1  # start has been sent, done has not
        usage = StubUsageTracking()

        with build_client(service, usage) as client:
            response = client.post("/simplify", json={"text": SOURCE})

        events = parse_lines(response.text)
        assert [event["event"] for event in events] == ["start", "done"]
        # The status code is long gone by the time the loop fails, so the stream itself
        # has to say so. Re-raising here would abort the body and discard this line.
        assert events[-1]["text"] == SOURCE
        assert events[-1]["converged"] is False
        assert events[-1]["scored"] is False
