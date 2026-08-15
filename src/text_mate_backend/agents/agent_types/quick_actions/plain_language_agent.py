"""The rewriter of the simplification loop.

This agent handles LLM-based text rewriting into Einfache Sprache (B1-A2) for German,
or simplified language for multilingual inputs, as part of the closed-loop pipeline
in :mod:`text_mate_backend.services.simplify_service`.

Swiss orthography (replacing ``ß`` with ``ss``) is applied selectively for German
rewrites in :meth:`PlainLanguageAgent.rewrite`.
"""

from typing import final, override

from dcc_backend_common.llm_agent import BaseAgent, Preprocessor
from dcc_backend_common.llm_agent.postprocessing import trim_text
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_utils import build_agent_metadata
from text_mate_backend.models.simplify_models import RewriteRequest
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.simplify_prompt import build_rewrite_prompt, build_system_message, is_german

OUTPUT_RULES_DE = """
Halte dich strikt an diese Ausgaberegeln:
- Gib nur reinen Text aus, keine HTML-Tags und kein Markdown.
- Gib keine Einleitung und keinen Schlusskommentar aus.
- Gib ausschliesslich den umgeschriebenen Text aus, sonst nichts.
- Trenne Absätze mit einer Leerzeile.
"""

OUTPUT_RULES_GENERIC = """
Strictly follow these output rules:
- Output plain text only, no HTML tags and no Markdown.
- Do not output an introduction or a closing comment.
- Output the rewritten text and nothing else.
- Separate paragraphs with a blank line.
"""


def to_swiss_orthography(text: str) -> str:
    """Replace ``ß`` with ``ss`` — Swiss German convention, German output only.

    >>> to_swiss_orthography("Straße")
    'Strasse'
    """
    return text.replace("ß", "ss")


@final
class PlainLanguageAgent(BaseAgent[RewriteRequest, str]):
    """Rewrites a text (or one paragraph of it) into Einfache Sprache, B1–A2."""

    def __init__(self, config: Configuration) -> None:
        super().__init__(config, deps_type=RewriteRequest, output_type=str, enable_thinking=False)

    @override
    def _get_postprocessors(self) -> list[Preprocessor]:
        """Everything ``BaseAgent`` does by default except ``replace_eszett``.

        Swiss orthography depends on the output language, which a postprocessor
        cannot see; :meth:`rewrite` applies it instead.
        """
        return [trim_text]

    @override
    def create_agent(self, model: Model) -> Agent[RewriteRequest, str]:
        agent = Agent[RewriteRequest, str](
            model=model,
            deps_type=RewriteRequest,
            output_type=str,
            name="Plain Language Agent",
            description="Rewrites text into Einfache Sprache (B1-A2) inside the readability loop",
            metadata=lambda ctx: build_agent_metadata(
                "simplify_rewrite",
                output_type="str",
                language=ctx.deps.language,
                attempt=ctx.deps.attempt,
                text_length=len(ctx.deps.text),
                chunked=ctx.deps.neighbour_context is not None,
            ),
        )

        @agent.instructions
        def get_instruction(ctx: RunContext[RewriteRequest]) -> str:
            german = is_german(ctx.deps.language)
            return f"{build_system_message(ctx.deps.language)}\n{OUTPUT_RULES_DE if german else OUTPUT_RULES_GENERIC}"

        return agent

    def build_prompt(self, request: RewriteRequest) -> str:
        """Assemble the user prompt for one attempt.

        Split out from :meth:`rewrite` so the prompt can be inspected in tests
        without an LLM.
        """
        return build_rewrite_prompt(
            request.text,
            request.language,
            score_reference=request.score_reference,
            issues=request.issues,
            previous_attempt=request.previous_attempt,
            passing_examples=request.passing_examples,
            neighbour_context=request.neighbour_context,
            exemplar_limit=request.exemplar_limit,
        )

    async def rewrite(self, request: RewriteRequest, temperature: float | None = 0.0) -> str:
        """Produce one rewrite. ``temperature`` is 0 on attempt 1 and higher on retries.

        A deterministic retry reproduces the failure, hence the schedule
        (section 5.3); ``BaseAgent`` merges per-call ``model_settings`` already.

        ``None`` omits the field entirely rather than sending ``temperature: null``,
        which vLLM rejects — the request then carries the server's own default, which
        is what the eval's ``--server-default-temperature`` needs in order to compare
        against a baseline that also sets none.
        """
        output = await self.run(
            self.build_prompt(request),
            deps=request,
            model_settings={} if temperature is None else {"temperature": temperature},
        )
        return to_swiss_orthography(output) if is_german(request.language) else output
