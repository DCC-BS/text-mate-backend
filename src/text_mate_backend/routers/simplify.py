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
from text_mate_backend.services.simplify_service import SimplifyService
from text_mate_backend.utils.auth import AuthSchema
from text_mate_backend.utils.usage_tracking import get_user_id

logger = get_logger("simplify_router")

#: JSON Lines: one compact JSON object per line, UTF-8, never ASCII-escaped
#: (the payload is German, French and Italian prose).
LINE_SEPARATOR = "\n"


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
        # Both languages are recorded, not just the one that wins: the client's hint
        # is its UI locale and the detected value comes from the text itself, so the
        # disagreement rate between them is the measurement that tells us whether the
        # hint was ever worth anything (section 1, T5.1).
        detected_language, _ = simplify_service.detect(data.text, data.language)
        usage_tracking_service.log_event(
            "text.simplify",
            get_user_id(current_user),
            text_length=len(data.text),
            detected_language=detected_language,
            hinted_language=data.language,
            # None when the client sent no hint. Comparing against a missing hint would
            # report a mismatch on every such request and make the metric meaningless.
            language_mismatch=(detected_language != data.language) if data.language else None,
        )

        async def event_stream() -> AsyncGenerator[str, None]:
            # NOTE: CancelOnDisconnect is not used here because StreamingResponse
            # evaluation happens after this handler returns; the ASGI server cancels
            # this task on disconnect and the service cancels its in-flight LLM calls
            # in response (see SimplifyService._run_chunked's finally block).
            try:
                async for event in simplify_service.simplify_stream(data.text, data.language):
                    yield event.model_dump_json() + LINE_SEPARATOR
            except asyncio.CancelledError:
                logger.info("Client disconnected from simplify JSON Lines stream")
                raise
            except Exception:
                # The 200 and the leading lines are already on the wire, so the failure
                # cannot be signalled as a status code without corrupting the stream.
                # It is signalled in the stream instead: a terminal `done` carrying the
                # unmodified original and `converged: false`, which leaves the client in
                # a defined state and loses nothing (the original is what it already has).
                #
                # Deliberately NOT re-raised, unlike /advisor/fix. Re-raising aborts the
                # response body, which would discard this very line — the one that
                # reports the failure. /advisor/fix streams bare text with no terminal
                # marker, so there an abort is the only signal available; here the
                # protocol has one, and it is worth more than a truncated connection.
                logger.exception("Unhandled error during simplify JSON Lines stream")
                yield (
                    json.dumps(
                        {
                            "event": "done",
                            "text": data.text,
                            "language": detected_language,
                            "scored": False,
                            "converged": False,
                            "unconverged_units": [],
                            "unconverged_ranges": [],
                        },
                        ensure_ascii=False,
                    )
                    + LINE_SEPARATOR
                )

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
