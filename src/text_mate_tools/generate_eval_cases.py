"""
Generate advisor eval cases with seeded rule violations (LLM-assisted).

For each batch of rules, an agent writes a realistic German text (Behördenbrief or
Verwaltungstext) that contains exactly one violation per rule, together with the
exhaustive ground-truth labels. Generated cases are validated (every labeled source
must occur in the text) and written to a staging directory for MANDATORY human review
before being moved into evals/advisor/cases/.

Usage (from the repository root):
    uv run --env-file .env src/text_mate_tools/generate_eval_cases.py --collection bundeskanzlei [options]

Options:
    --collection NAME       Rule collection to draw rules from (required)
    --rules-per-case N      Number of rules violated per generated text (default: 3)
    --max-cases N           Stop after N cases (default: all rules covered once)
    --output DIR            Staging output directory (default: staging/evals)

Environment:
    Same .env as the backend (LLM_API_KEY, LLM_URL, LLM_MODEL, ...).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dcc_backend_common.llm_agent import BaseAgent
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from text_mate_backend.models.rule_models import Rule, RulesContainer
from text_mate_backend.utils.configuration import Configuration
from text_mate_tools.advisor_eval.models import EvalCase, ExpectedViolation

RULES_DIR = Path("assets/docs/rules")
MAX_RETRIES = 2

PROMPT = """Du bist ein Testdaten-Autor für ein Redaktionswerkzeug. Schreibe einen \
realistischen, kurzen deutschen Verwaltungstext (Behördenbrief oder Mitteilung, 80–180 \
Wörter), der gegen jede der untenstehenden Regeln GENAU EINMAL verstösst — und sonst \
gegen KEINE der Regeln.

## Anforderungen
1. Der Text muss natürlich klingen; die Verstösse dürfen nicht künstlich wirken.
2. Für jeden Verstoss gib in `expected` den **exakten Textausschnitt** (`source`) an, \
Wort für Wort wie im Text, minimal gehalten (das Wort oder die kurze Wendung, die den \
Verstoss enthält).
3. `rule_name` exakt wie in der Regeldokumentation.
4. Kommt der Ausschnitt mehrfach im Text vor, gib mit `occurrence` an, das wievielte \
Vorkommen gemeint ist (1-basiert).
5. Ausser den geforderten Verstössen muss der Text alle unten aufgeführten Regeln \
einhalten. Verwende Schweizer Hochdeutsch (kein ß, ausser die Regel verlangt einen \
ß-Verstoss).

## Regeln, gegen die verstossen werden soll
{rules}
"""


class GeneratedCase(BaseModel):
    """LLM output: text plus exhaustive labels."""

    text: str = Field(description="Der generierte Text")
    expected: list[ExpectedViolation] = Field(description="Alle eingebauten Verstösse mit exakten Textausschnitten")


class CaseGeneratorAgent(BaseAgent[RulesContainer, GeneratedCase]):
    def __init__(self, config: Configuration):
        super().__init__(
            config,
            deps_type=RulesContainer,
            output_type=GeneratedCase,
            enable_thinking=True,
        )

    def create_agent(self, model: Model) -> Agent[RulesContainer, GeneratedCase]:
        agent = Agent(model, deps_type=RulesContainer, output_type=GeneratedCase)

        @agent.instructions
        def instructions(ctx: RunContext[RulesContainer]) -> str:
            return PROMPT.format(rules=ctx.deps.model_dump_json())

        return agent


def load_collection_rules(collection: str) -> list[Rule]:
    rules: list[Rule] = []
    for json_file in sorted(RULES_DIR.glob("*.json")):
        container = RulesContainer.model_validate_json(json_file.read_text())
        rules.extend(rule for rule in container.rules if rule.collection == collection)
    if not rules:
        raise SystemExit(f"No rules found for collection '{collection}' in {RULES_DIR}")
    return rules


def validate_generated(case: GeneratedCase, rules: list[Rule]) -> list[str]:
    """Return a list of problems; empty means the case is usable."""
    problems: list[str] = []
    rule_names = {rule.name for rule in rules}
    for expected in case.expected:
        if expected.rule_name not in rule_names:
            problems.append(f"unknown rule name '{expected.rule_name}'")
        occurrences = case.text.count(expected.source) if expected.source else 0
        if occurrences < expected.occurrence:
            problems.append(f"source '{expected.source[:60]}' occurrence {expected.occurrence} not found in text")
    labeled = {expected.rule_name for expected in case.expected}
    for rule in rules:
        if rule.name not in labeled:
            problems.append(f"no violation labeled for rule '{rule.name}'")
    return problems


async def generate_case(agent: CaseGeneratorAgent, rules: list[Rule], case_id: str, collection: str) -> EvalCase | None:
    for attempt in range(1 + MAX_RETRIES):
        generated = await agent.run(deps=RulesContainer(rules=rules))
        problems = validate_generated(generated, rules)
        if not problems:
            return EvalCase(
                id=case_id,
                description=f"Generated case seeding: {', '.join(rule.name for rule in rules)}",
                collections=[collection],
                text=generated.text,
                expected=generated.expected,
            )
        print(f"      ⚠️ attempt {attempt + 1} invalid: {'; '.join(problems)}")
    return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate advisor eval cases with seeded violations.")
    parser.add_argument("--collection", required=True)
    parser.add_argument("--rules-per-case", type=int, default=3)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path("staging/evals"))
    args = parser.parse_args()

    config = Configuration.from_env()
    agent = CaseGeneratorAgent(config)
    rules = load_collection_rules(args.collection)
    args.output.mkdir(parents=True, exist_ok=True)

    batches = [rules[i : i + args.rules_per_case] for i in range(0, len(rules), args.rules_per_case)]
    if args.max_cases is not None:
        batches = batches[: args.max_cases]

    print(f"Generating {len(batches)} case(s) for collection '{args.collection}'")
    written = 0
    for index, batch in enumerate(batches, 1):
        case_id = f"gen-{args.collection}-{index:03d}"
        print(f"   ⚙️ {case_id}: {', '.join(rule.name for rule in batch)}")
        case = await generate_case(agent, batch, case_id, args.collection)
        if case is None:
            print(f"      ❌ giving up on {case_id} after {1 + MAX_RETRIES} attempts")
            continue
        out_file = args.output / f"{case_id}.json"
        out_file.write_text(json.dumps(case.model_dump(), ensure_ascii=False, indent=2) + "\n")
        written += 1
        print(f"      ✅ wrote {out_file}")

    print(f"\nDone: {written}/{len(batches)} cases written to {args.output}")
    print("Review each case manually, then move approved files to evals/advisor/cases/.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
