from typing import override

from dcc_backend_common.llm_agent import BaseAgent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_utils import build_agent_metadata
from text_mate_backend.models.fix_models import FixRequest
from text_mate_backend.utils.configuration import Configuration

INSTRUCTION = """Du bist ein Experte für Textkorrektur. Du erhältst einen Eingabetext und eine \
Liste von Korrekturen. Deine Aufgabe ist es, einen vollständigen, korrigierten Text \
auszugeben, in dem alle Korrekturen angewendet wurden.

## Arbeitsweise
1. Wende für jeden Thread mit `source` und `proposal` den Vorschlag an.
2. Nutze `reason` und `notes` als zusätzlichen Kontext, um die Ersetzung sinngemäss und \
sprachlich passend einzubauen. Falls ein Vorschlag unpassend oder unvollständig erscheint, \
dürfen die `reason`/`notes` eine leicht angepasste, sinnvollere Formulierung motivieren, \
die der Absicht des Autors entspricht.
3. Behalte den übrigen Text unverändert bei — inklusive Formatierung, Absätzen und Satzzeichen.
4. Gib ausschliesslich den korrigierten Gesamtext aus. Keine Erklärungen, keine Einleitung, \
keinen Schlusskommentar, kein Markdown, keine HTML-Tags.

## Eingabetext
---------------
{text}
---------------

## Korrekturthreads
---------------
{threads}
---------------

Antworte in der Sprache des Eingabetextes."""


class FixAgent(BaseAgent[FixRequest, str]):
    def __init__(self, config: Configuration):
        super().__init__(config, deps_type=FixRequest, output_type=str)

    @override
    def create_agent(self, model: Model) -> Agent[FixRequest, str]:
        agent = Agent(
            model=model,
            deps_type=FixRequest,
            output_type=str,
            name="Fix Agent",
            description="Applies correction threads to an input text and returns the fully corrected text",
            metadata=lambda ctx: build_agent_metadata(
                "fix",
                output_type="str",
                text_length=len(ctx.deps.text),
                thread_count=len(ctx.deps.threads),
            ),
        )

        @agent.instructions
        def get_instruction(ctx: RunContext[FixRequest]) -> str:
            threads_json = "[" + ", ".join(t.model_dump_json() for t in ctx.deps.threads) + "]"
            return INSTRUCTION.format(text=ctx.deps.text, threads=threads_json)

        return agent
