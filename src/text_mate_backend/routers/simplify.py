"""``POST /simplify`` — the streaming entry point of the simplification loop.

Replaces ``POST /quick-action`` with ``plain_language``, which was one unverified
LLM call. The wire format is JSON Lines, one event object per line, exactly as
``docs/simplify_redesign.md`` section 4.7 specifies and structurally identical to
``POST /advisor/validate`` so the frontend's line parser is reused::

    {"event":"start","language":"de","score_label":"ZIX","scored":true,"mode":"whole", ...}
    {"event":"progress","attempt":2,"stage":"readability", ...}
    {"event":"chunk_done","index":3,"text":"...", ...}      // CHUNKED only, FINAL
    {"event":"done","text":"...","converged":true, ...}

Three properties of the stream that the route is responsible for:

* **``done`` always arrives, and always carries the fully assembled text.** In
  WHOLE mode a client can ignore everything but ``progress`` and ``done``.
* **``chunk_done`` is final.** The service only emits it once a unit can no longer
  change, so the UI never has to retract text it has already shown.
* **Nothing is buffered.** ``X-Accel-Buffering: no`` keeps the reverse proxy from
  holding the progress events back until the run finishes, which would defeat the
  entire point of streaming a loop that can take minutes.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated

from dcc_backend_common.logger import get_logger
from dcc_backend_common.usage_tracking import UsageTrackingService
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.params import Security
from fastapi.responses import StreamingResponse
from fastapi_azure_auth.user import User

from text_mate_backend.container import Container
from text_mate_backend.models.simplify_models import SimplifyInput
from text_mate_backend.services.simplify_service import ModelUnavailableError, SimplifyService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.usage_tracking import get_user_id

logger = get_logger("simplify_router")

#: JSON Lines: one compact JSON object per line, UTF-8, never ASCII-escaped
#: (the payload is German, French and Italian prose).
LINE_SEPARATOR = "\n"


def _failure_done(text: str, language: str | None) -> str:
    """The terminal ``done`` for a run that broke: the original back, marked as failed.

    ``rewrite_failures`` is what stops this from reading as a success. Without it the
    client sees an unchanged text, finds no diff hunks, and reports "nothing to change"
    — a reassuring message for a run that never produced anything. The exact count is
    unknown here (the exception ended the run), so it is reported as at least one, which
    is what the field is used for: zero or not zero.
    """
    return json.dumps(
        {
            "event": "done",
            "text": text,
            "language": language,
            "scored": False,
            "converged": False,
            "unconverged_units": [],
            "unconverged_ranges": [],
            "rewrite_failures": 1,
        },
        ensure_ascii=False,
    )


@inject
def create_router(
    simplify_service: SimplifyService = Provide[Container.simplify_service],
    auth_scheme: AuthSchema = Provide[Container.auth_scheme],
    usage_tracking_service: UsageTrackingService = Provide[Container.usage_tracking_service],
) -> APIRouter:
    logger.debug("Creating simplify router")
    router: APIRouter = APIRouter(prefix="/simplify", tags=["simplify"])

    @router.post("", dependencies=[Security(auth_scheme)])
    async def simplify_text(
        data: SimplifyInput,
        current_user: Annotated[User | None, Depends(auth_scheme)],
    ) -> StreamingResponse:
        detected_language, _ = simplify_service.detect(data.text, data.language)
        usage_tracking_service.log_event(
            "text.simplify",
            get_user_id(current_user),
            text_length=len(data.text),
            detected_language=detected_language,
            hinted_language=data.language,
            language_mismatch=(detected_language != data.language) if data.language else None,
        )

        async def event_stream() -> AsyncGenerator[str, None]:
            # StreamingResponse task is cancelled by ASGI server on disconnect
            try:
                async for event in simplify_service.simplify_stream(data.text, data.language):
                    yield event.model_dump_json() + LINE_SEPARATOR
            except asyncio.CancelledError:
                logger.info("Client disconnected from simplify JSON Lines stream")
                raise
            except ModelUnavailableError:
                logger.error("Simplify aborted: the model is unreachable")
                yield _failure_done(data.text, detected_language) + LINE_SEPARATOR
            except Exception:
                # Emit terminal failure event over open stream without re-raising to avoid stream truncation
                logger.exception("Unhandled error during simplify JSON Lines stream")
                yield _failure_done(data.text, detected_language) + LINE_SEPARATOR

        return StreamingResponse(
            event_stream(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    logger.debug("Simplify router configured")
    return router
