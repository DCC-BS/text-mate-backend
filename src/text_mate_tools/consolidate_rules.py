"""
Standalone rule consolidation script.

Loads rules from staging JSON files, runs the consolidation LLM pass
(batched for large sets), and writes the consolidated output.

Usage:
    uv run --env-file .env src/text_mate_tools/consolidate_rules.py <input.json> [<input.json> ...] [--output OUTPUT_FILE]

Example:
    uv run --env-file .env src/text_mate_tools/consolidate_rules.py staging/rules/schreibweisungen.json
    uv run --env-file .env src/text_mate_tools/consolidate_rules.py staging/rules/*.json --output staging/rules/consolidated.json

Environment:
    LLM_API_KEY       API key for the LLM
    LLM_URL           LLM endpoint URL
    LLM_MODEL         LLM model name
"""  # noqa: E501

import argparse
import asyncio
import sys
import time
from pathlib import Path

from text_mate_backend.models.rule_models import Rule, RulesContainer
from text_mate_backend.utils.configuration import Configuration
from text_mate_tools.rule_utils import (
    ConsolidationAgent,
    consolidate_rules,
    deduplicate_rules,
    print_quality_report,
)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate extracted rules from staging JSON files.")
    parser.add_argument(
        "inputs",
        nargs="+",
        type=str,
        help="Path(s) to input JSON file(s) containing rules in RulesContainer format",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: overwrite first input file)",
    )
    args = parser.parse_args()

    input_paths: list[Path] = []
    for inp in args.inputs:
        path = Path(inp)
        if not path.exists():
            print(f"❌ ERROR: File not found: {inp}")
            sys.exit(1)
        if not path.is_file() or path.suffix.lower() != ".json":
            print(f"❌ ERROR: Not a JSON file: {inp}")
            sys.exit(1)
        input_paths.append(path)

    all_rules: list[Rule] = []
    for path in input_paths:
        container = RulesContainer.model_validate_json(path.read_text())
        print(f"📥 Loaded {len(container.rules)} rules from {path.name}")
        all_rules.extend(container.rules)

    print(f"\n📊 Total rules loaded: {len(all_rules)} from {len(input_paths)} file(s)")

    all_rules, removed = deduplicate_rules(all_rules)
    if removed > 0:
        print(f"🔄 Removed {removed} duplicate rule(s)")

    config = Configuration.from_env()
    agent = ConsolidationAgent(config)

    start_time = time.time()
    all_rules = await consolidate_rules(all_rules, agent)
    elapsed = time.time() - start_time

    all_rules, removed = deduplicate_rules(all_rules)
    if removed > 0:
        print(f"🔄 Removed {removed} duplicate rule(s)")

    print_quality_report(all_rules, "consolidated")

    output_path = Path(args.output) if args.output else input_paths[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(RulesContainer(rules=all_rules).model_dump_json(indent=2))

    print("\n✨ Consolidation complete!")
    print(f"📊 Final rule count: {len(all_rules)}")
    print(f"⏱️ Time: {elapsed:.2f}s")
    print(f"💾 Saved to: {output_path.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
