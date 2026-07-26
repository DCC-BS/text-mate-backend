"""Shared utilities for rule extraction, consolidation, and quality analysis."""

from dcc_backend_common.llm_agent import BaseAgent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.models.rule_models import Rule, RulesContainer
from text_mate_backend.utils.configuration import Configuration

SHORT_DESC_THRESHOLD = 50
LONG_DESC_THRESHOLD = 400
CONSOLIDATE_BATCH_SIZE = 50

consolidation_prompt = """Du bist ein Experte für Redaktionsrichtlinien. Du erhältst eine Liste von \
extrahierten Regeln und sollst sie konsolidieren.

## Extrahierte Regeln
{rules}

## Deine Aufgabe
Durchsuche die Regeln nach Redundanzen und führe überflüssige Regeln zusammen. \
Sei dabei **konservativ**: wenn du unsicher bist, ob zwei Regeln zusammengehören, \
lasse sie getrennt.

### Was zusammengeführt werden soll:
1. **Exakte Duplikate** – dieselbe Regel, die versehentlich mehrfach extrahiert wurde.
2. **Near-Duplikate** – dieselbe inhaltliche Regel mit leicht abweichender Formulierung.
3. **Regel + Ausnahme** – eine Grundregel und eine separate Regel, die eine \
Ausnahme oder Ergänzung dazu beschreibt. Diese gehören zusammen.
   Beispiel: «Kurze Zahlen ausschreiben» + «Mehrere Zahlen im Zusammenhang \
in Ziffern» → eine Regel mit integrierter Ausnahme.

### Was **nicht** zusammengeführt werden soll:
- Regeln, die thematisch verwandt, aber inhaltlich unterschiedlich sind \
(z. B. «unnötige Anglizismen ersetzen» und «etablierte Anglizismen beibehalten»).
- Regeln, die zwar dasselbe Thema behandeln, aber unterschiedliche Verstösse \
beschreiben.

### Beim Zusammenführen:
- Kombiniere die Beschreibungen zu einer präzisen, vollständigen Beschreibung.
- Wähle das passendste Beispiel oder kombiniere die Beispiele.
- Verwende als `file_name` und `page_number` die Quelle der primären Regel.
- Gib der zusammengeführten Regel einen klaren, beschreibenden Namen (max. 80 Zeichen).

## Anforderungen an jede Regel (auch unveränderte):
- **name**: Eindeutig, beschreibend (max. 80 Zeichen).
- **description**: 50–400 Zeichen, beschreibt explizit den Verstoss.
- **example**: Format `Falsch: ... | Richtig: ...`
- **file_name**, **page_number**, **collection**: aus dem Original übernehmen.
- Kein «ß» – verwende immer «ss».

Gib alle Regeln (sowohl die zusammengeführten als auch die unveränderten) als \
vollständige Liste zurück."""


class ConsolidationAgent(BaseAgent[RulesContainer, RulesContainer]):
    def __init__(self, config: Configuration):
        super().__init__(
            config,
            deps_type=RulesContainer,
            output_type=RulesContainer,
            enable_thinking=True,
        )

    def create_agent(self, model: Model) -> Agent[RulesContainer, RulesContainer]:
        agent = Agent(model, deps_type=RulesContainer, output_type=RulesContainer)

        @agent.instructions
        def instructions(ctx: RunContext[RulesContainer]) -> str:
            return consolidation_prompt.format(rules=ctx.deps.model_dump_json())

        return agent


def deduplicate_rules(rules: list[Rule]) -> tuple[list[Rule], int]:
    seen: set[str] = set()
    unique: list[Rule] = []
    for rule in rules:
        key = rule.name.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(rule)
    return unique, len(rules) - len(unique)


def print_quality_report(rules: list[Rule], label: str) -> None:
    if not rules:
        return

    desc_lens = [len(r.description) for r in rules]
    short = [r for r in rules if len(r.description) < SHORT_DESC_THRESHOLD]
    long_ = [r for r in rules if len(r.description) > LONG_DESC_THRESHOLD]
    weak_ex = [r for r in rules if "falsch" not in r.example.lower() or "richtig" not in r.example.lower()]

    print(f"\n   📋 Quality report ({label}):")
    print(f"      Rules: {len(rules)}")
    print(f"      Avg description length: {sum(desc_lens) // len(desc_lens)} chars")
    if short:
        print(f"      ⚠️  {len(short)} rule(s) with short description (<{SHORT_DESC_THRESHOLD} chars):")
        for r in short:
            print(f"         - {r.name} ({len(r.description)} chars)")
    if long_:
        print(f"      ⚠️  {len(long_)} rule(s) with long description (>{LONG_DESC_THRESHOLD} chars):")
        for r in long_:
            print(f"         - {r.name} ({len(r.description)} chars)")
    if weak_ex:
        print(f"      ⚠️  {len(weak_ex)} rule(s) with weak example (missing 'Falsch:'/'Richtig:'):")
        for r in weak_ex:
            preview = r.example[:60] + "..." if len(r.example) > 60 else r.example or "(empty)"
            print(f"         - {r.name}: {preview}")
    if not short and not long_ and not weak_ex:
        print("      ✅ All rules pass quality checks")


async def _consolidate_single(rules: list[Rule], agent: ConsolidationAgent) -> list[Rule]:
    """Run a single consolidation LLM call and print the diff."""
    before_names = {r.name for r in rules}

    try:
        response = await agent.run(deps=RulesContainer(rules=rules))
        consolidated = response.rules
    except Exception as e:
        print(f"      ⚠️ Consolidation failed: {e}. Keeping unconsolidated rules.")
        return rules

    after_names = {r.name for r in consolidated}
    removed = sorted(before_names - after_names)
    added = sorted(after_names - before_names)

    for name in removed:
        print(f'      ➖ Removed/merged: "{name}"')
    for name in added:
        print(f'      ➕ New: "{name}"')

    print(f"      ✅ {len(rules)} → {len(consolidated)} rules")
    return consolidated


async def consolidate_rules(rules: list[Rule], agent: ConsolidationAgent) -> list[Rule]:
    """Consolidate rules, batching when the set exceeds CONSOLIDATE_BATCH_SIZE."""
    if len(rules) < 2:
        return rules

    if len(rules) <= CONSOLIDATE_BATCH_SIZE:
        print(f"   🔀 Consolidating {len(rules)} rules...")
        return await _consolidate_single(rules, agent)

    n_chunks = (len(rules) + CONSOLIDATE_BATCH_SIZE - 1) // CONSOLIDATE_BATCH_SIZE
    print(f"   🔀 Consolidating {len(rules)} rules in {n_chunks} batches of {CONSOLIDATE_BATCH_SIZE}...")

    consolidated: list[Rule] = []
    for i in range(0, len(rules), CONSOLIDATE_BATCH_SIZE):
        chunk = rules[i : i + CONSOLIDATE_BATCH_SIZE]
        batch_num = i // CONSOLIDATE_BATCH_SIZE + 1
        print(f"      📦 Batch {batch_num}/{n_chunks} ({len(chunk)} rules)")
        result = await _consolidate_single(chunk, agent)
        consolidated.extend(result)

    if len(consolidated) > 1:
        print(f"      🔁 Final cross-batch pass ({len(consolidated)} rules)...")
        consolidated = await _consolidate_single(consolidated, agent)

    print(f"   ✅ Consolidated {len(rules)} → {len(consolidated)} rules")
    return consolidated
