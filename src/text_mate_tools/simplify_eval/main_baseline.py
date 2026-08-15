"""The **pre-redesign** baseline: `main`'s single-shot, single-prompt simplification.

This is not ``--simplifier simplify_single_shot``. That one is the *new* pipeline with
the retry round switched off, and it still carries everything else the redesign added:
the reconciled Basel-Stadt/Bundeskanzlei rule set, the unit chunker, the score reference
in the prompt, the readability gate. Comparing it against ``simplify`` isolates the
retry, which is the only question ``run_simplify_eval``'s docstring set out to answer.

The question this module answers is the other one: **what did the whole redesign buy
over what shipped on `main`?** So it reproduces the `main` path end to end —

* one LLM call for the entire document, whatever its length (no chunking, §14.3),
* no readability measurement anywhere: nothing scores the input, nothing scores the
  output, so nothing can retry (``converged`` is therefore always ``False``; the harness
  scores both sides itself, which is what makes the two runs comparable),
* the `main` prompt verbatim — ``SYSTEM_MESSAGE_ES``, ``CLAUDE_TEMPLATE_ES``,
  ``RULES_ES``, ``REWRITE_COMPLETE`` as they read at commit ``5a5079a`` — including the
  Zurich rule formulations the redesign later overrode (``docs/simplify_rules_audit.md``),
* the ``QuickActionBaseAgent`` instruction envelope `main` wrapped around it (language
  instruction plus output rules),
* ``POST /quick-action`` with ``plain_language``'s model settings: no ``temperature``
  override, so the server default applies, exactly as on `main`.

The constants below are **copies, not imports**. Importing them from
``text_mate_backend.utils.easy_language`` would silently re-point the baseline at the
current branch's reconciled rules the moment anyone edits that file, and a baseline that
moves with the thing it measures is not a baseline. They were extracted mechanically from
``git show main:src/text_mate_backend/utils/easy_language.py``; regenerate them the same
way if `main` ever changes, and say so in the report when you do.

One deliberate deviation: `main`'s ``PlainLanguageAgent`` also registered a
``check_readability_score`` tool (word/sentence counts, computed in Python). It is not
reproduced. It gave the model four descriptive numbers with no threshold to compare them
against and no consequence attached to the answer, and reproducing it would make the
baseline's call count depend on whether this vLLM build advertises tool calling at all —
turning "one call, one prompt" into something that varies per deployment. Its absence
cannot make the baseline look worse: nothing in `main` acted on the tool's output.
"""

from typing import final, override

from dcc_backend_common.llm_agent import BaseAgent
from dcc_backend_common.llm_agent.base_agent import UserPrompt
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.agents.agent_utils import build_agent_metadata, get_language_instruction
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration
from text_mate_tools.simplify_eval.models import SimplifyOutput

# ruff: noqa: E501  # verbatim German prompt text from `main` — reflowing it would change the prompt

# =============================================================================
# `main`'s PROMPT, VERBATIM (git show main:src/text_mate_backend/utils/easy_language.py)
# =============================================================================

MAIN_SYSTEM_MESSAGE_ES: str = (
    "Du bist ein hilfreicher Assistent, der Texte in Einfache Sprache, Sprachniveau B1 bis A2, "
    "umschreibt. Sei immer wahrheitsgemäß und objektiv. Schreibe nur das, was du sicher aus dem "
    "Text des Benutzers weisst. Arbeite die Texte immer vollständig durch und kürze nicht. "
    "Mache keine Annahmen. Schreibe einfach und klar und immer in deutscher Sprache. "
)

MAIN_RULES_ES: str = """- Schreibe kurze Sätze mit höchstens 12 Wörtern.
- Beschränke dich auf eine Aussage, einen Gedanken pro Satz.
- Verwende aktive Sprache anstelle von Passiv.
- Formuliere grundsätzlich positiv und bejahend.
- Strukturiere den Text übersichtlich mit kurzen Absätzen.
- Verwende einfache, kurze, häufig gebräuchliche Wörter.
- Wenn zwei Wörter dasselbe bedeuten, verwende das kürzere und einfachere Wort.
- Vermeide Füllwörter und unnötige Wiederholungen.
- Erkläre Fachbegriffe und Fremdwörter.
- Schreibe immer einfach, direkt und klar. Vermeide komplizierte Konstruktionen und veraltete Begriffe. Vermeide «Behördendeutsch».
- Benenne Gleiches immer gleich. Verwende für denselben Begriff, Gegenstand oder Sachverhalt immer dieselbe Bezeichnung. Wiederholungen von Begriffen sind in Texten in Einfacher Sprache normal.
- Vermeide Substantivierungen. Verwende stattdessen Verben und Adjektive.
- Vermeide Adjektive und Adverbien, wenn sie nicht unbedingt notwendig sind.
- Wenn du vier oder mehr Wörter zusammensetzt, setzt du Bindestriche. Beispiel: «Motorfahrzeug-Ausweispflicht».
- Achte auf die sprachliche Gleichbehandlung von Mann und Frau. Verwende immer beide Geschlechter oder schreibe geschlechtsneutral.
- Vermeide Abkürzungen grundsätzlich. Schreibe stattdessen die Wörter aus. Z.B. «10 Millionen» statt «10 Mio.», «200 Kilometer pro Stunde» statt «200 km/h», «zum Beispiel» statt «z.B.», «30 Prozent» statt «30 %», «2 Meter» statt «2 m», «das heisst» statt «d.h.».
- Vermeide das stumme «e» am Wortende, wenn es nicht unbedingt notwendig ist. Zum Beispiel: «des Fahrzeugs» statt «des Fahrzeuges».
- Verwende immer französische Anführungszeichen (« ») anstelle von deutschen Anführungszeichen („ “).
- Gliedere Telefonnummern mit vier Leerzeichen. Z.B. 044 123 45 67. Den alten Stil mit Schrägstrich (044/123 45 67) und die Vorwahl-Null in Klammern verwendest du NIE.
- Formatiere Datumsangaben immer so: 1. Januar 2022, 15. Februar 2022.
- Jahreszahlen schreibst du immer vierstellig aus: 2022, 2025-2030.
- Formatiere Zeitangaben immer «Stunden Punkt Minuten Uhr». Verwende keinen Doppelpunkt, um Stunden von Minuten zu trennen. Ergänze immer .00 bei vollen Stunden. Beispiele: 9.25 Uhr (NICHT 9:30), 10.30 Uhr (NICHT 10:00), 14.00 Uhr (NICHT 14 Uhr), 15.45 Uhr, 18.00 Uhr, 20.15 Uhr, 22.30 Uhr.
- Zahlen bis 12 schreibst du aus. Ab 13 verwendest du Ziffern.
- Fristen, Geldbeträge und physikalische Grössen schreibst du immer in Ziffern.
- Zahlen, die zusammengehören, schreibst du immer in Ziffern. Beispiel: 5-10, 20 oder 30.
- Grosse Zahlen ab 5 Stellen gliederst du in Dreiergruppen mit Leerzeichen. Beispiel: 1 000 000.
- Achtung: Identifikationszahlen übernimmst du 1:1. Beispiel: Stammnummer 123.456.789, AHV-Nummer 756.1234.5678.90, Konto 01-100101-9.
- Verwende das Komma, dass das deutsche Dezimalzeichen ist. Überflüssige Nullen nach dem Komma schreibst du nicht. Beispiel: 5,5 Millionen, 3,75 Prozent, 1,5 Kilometer, 2,25 Stunden.
- Vor Franken-Rappen-Beträgen schreibst du immer «CHF». Nur nach ganzen Franken-Beträgen darfst du «Franken» schreiben. Bei Franken- Rappen-Beträgen setzt du einen Punkt als Dezimalzeichen. Anstatt des Null-Rappen-Strichs verwendest du «.00» oder lässt die Dezimalstellen weg. Z.B. 20 Franken, CHF 20, CHF 2.00, CHF 12.50, aber CHF 45,2 Millionen, EUR 14,90.
- Die Anrede mit «Sie» schreibst du immer gross. Beispiel: «Sie haben»."""

MAIN_REWRITE_COMPLETE: str = """- Achte immer sehr genau darauf, dass ALLE Informationen aus dem schwer verständlichen Text in deinem verständlicheren Text enthalten sind. Kürze niemals Informationen. Wo sinnvoll kannst du zusätzliche Beispiele hinzufügen, um den Text verständlicher zu machen und relevante Inhalte zu konkretisieren."""

MAIN_CLAUDE_TEMPLATE_ES: str = """Hier ist ein schwer verständlicher Text, den du vollständig in Einfache Sprache, Sprachniveau B1 bis A2, umschreiben sollst:

<schwer-verständlicher-text>
{prompt}
</schwer-verständlicher-text>

Bitte lies den Text sorgfältig durch und schreibe ihn vollständig in Einfache Sprache um.

Beachte dabei folgende Regeln:

{completeness}
{rules}

Formuliere den Text jetzt in Einfache Sprache, Sprachniveau B1 bis A2, um."""

MAIN_OUTPUT_RULES: str = """Halte dich strikt an diese Ausgaberegeln:
                - Gib nur reinen Text aus, keine HTML-Tags und kein Markdown.
                - Gib keine Einleitung und keinen Schlusskommentar aus.
                - Gib ausschliesslich das Ergebnis aus, keinen weiteren Text.
                - Füge keine zusätzlichen Informationen oder Erklärungen hinzu."""
"""The envelope ``QuickActionBaseAgent.create_agent`` wrapped every quick action in.

Indentation included: it is inside an f-string triple quote on `main` and reaches the
model exactly like this. Reflowing it would be a change to the prompt under test.
"""


@final
class MainPlainLanguageAgent(BaseAgent[QuickActionContext, str]):
    """`main`'s ``PlainLanguageAgent``, reassembled from its two files.

    On `main` this class inherited the instruction envelope from
    ``QuickActionBaseAgent``; here the envelope is inlined, because that base class
    also exists on this branch and has moved on. The text the model receives is the
    same on both sides: system message, language instruction, output rules.
    """

    def __init__(self, config: Configuration) -> None:
        super().__init__(config, deps_type=QuickActionContext, output_type=str, enable_thinking=False)

    @override
    def create_agent(self, model: Model) -> Agent[QuickActionContext, str]:
        agent = Agent[QuickActionContext, str](
            model=model,
            deps_type=QuickActionContext,
            output_type=str,
            name="Plain Language Agent (main baseline)",
            description="Rewrites text into plain language (main's single-shot quick action)",
            metadata=lambda ctx: build_agent_metadata(
                "quick_action",
                output_type="str",
                action="Plain Language Agent (main baseline)",
                language=ctx.deps.language,
                text_length=len(ctx.deps.text),
            ),
        )

        @agent.instructions
        def create_instruction(ctx: RunContext[QuickActionContext]) -> str:
            return f"""
                {MAIN_SYSTEM_MESSAGE_ES}

                {get_language_instruction(ctx.deps.language)}

                {MAIN_OUTPUT_RULES}
                """

        return agent

    @override
    def process_prompt(self, prompt: UserPrompt, deps: QuickActionContext | None) -> UserPrompt:
        return MAIN_CLAUDE_TEMPLATE_ES.format(prompt=prompt, completeness=MAIN_REWRITE_COMPLETE, rules=MAIN_RULES_ES)


@final
class MainSingleShotSimplifier:
    """``Simplifier`` Protocol over :class:`MainPlainLanguageAgent` — one call, no loop.

    ``converged=False`` is reported unconditionally and is **not** a failure signal: the
    baseline has no notion of a target band, so it can neither claim nor deny reaching
    one. Read this simplifier's column in the report through ``documents in target``,
    which the harness computes from the returned text with the same ZIX scorer it uses
    on every other simplifier, and ignore ``all units converged`` for it.
    """

    name = "main_single_shot"

    def __init__(self, config: Configuration) -> None:
        self.agent = MainPlainLanguageAgent(config)

    async def __call__(self, text: str, language: str) -> SimplifyOutput:
        context = QuickActionContext[dict](text=text, options="", language=language)
        rewritten = await self.agent.run(text, deps=context)
        usable = rewritten.strip() if rewritten else ""
        return SimplifyOutput(
            # An empty answer falls back to the source, matching what every other
            # simplifier does with a failed rewrite: the run is measured as "changed
            # nothing", not dropped from the corpus.
            text=usable or text,
            attempts=1,
            llm_calls=1,
            converged=False,
            # No mode of its own: `main` had no chunking, so the harness's own
            # size-derived mode is what puts this run in the same bucket as the
            # pipeline runs it is compared against.
            mode=None,
        )
