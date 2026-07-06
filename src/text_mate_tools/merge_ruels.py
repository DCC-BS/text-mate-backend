"""
Merge multiple rule-container JSON files into a single file.

Reads one or more input files (each a JSON object with a top-level "rules"
array), concatenates their "rules" arrays, and writes the combined object
to --output. Glob patterns are supported alongside explicit file paths.

Usage:
    uv run python src/text_mate_tools/merge_ruels.py <input.json> [<input.json> ...] [--glob '<pattern>'] --output OUTPUT_FILE

Example:
    uv run python src/text_mate_tools/merge_ruels.py staging/rules/a.json staging/rules/b.json --output staging/rules/merged.json
    uv run python src/text_mate_tools/merge_ruels.py 'staging/rules/*.json' --output staging/rules/merged.json
"""  # noqa: E501

import argparse
import glob
import json
import sys
from pathlib import Path


def expand_inputs(inputs: list[str]) -> list[Path]:
    """Expand each input arg: treat as a glob pattern if it contains glob
    characters, otherwise treat as a literal path. Returns a flat list of
    Paths (may contain duplicates across args)."""
    paths: list[Path] = []
    for arg in inputs:
        if any(ch in arg for ch in "*?["):
            matched = sorted(glob.glob(arg))
            if not matched:
                print(f"❌ ERROR: Glob pattern matched no files: {arg}")
                sys.exit(1)
            paths.extend(Path(m) for m in matched)
        else:
            paths.append(Path(arg))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge multiple rule-container JSON files into a single file.")
    parser.add_argument(
        "inputs",
        nargs="+",
        type=str,
        help='Path(s) to input JSON file(s) with a top-level {"rules": [...]} object, or glob patterns.',
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output file path for the merged JSON object.",
    )
    args = parser.parse_args()

    input_paths = expand_inputs(args.inputs)

    validated: list[Path] = []
    for path in input_paths:
        if not path.exists():
            print(f"❌ ERROR: File not found: {path}")
            sys.exit(1)
        if not path.is_file() or path.suffix.lower() != ".json":
            print(f"❌ ERROR: Not a JSON file: {path}")
            sys.exit(1)
        validated.append(path)

    input_paths = validated

    if not input_paths:
        print("❌ ERROR: No input files provided.")
        sys.exit(1)

    merged: list = []
    for path in input_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"❌ ERROR: Failed to parse JSON in {path}: {e}")
            sys.exit(1)

        if not isinstance(data, dict) or "rules" not in data:
            print(f'❌ ERROR: Expected a JSON object with a "rules" key in {path}, got {type(data).__name__}')
            sys.exit(1)

        rules = data["rules"]
        if not isinstance(rules, list):
            print(f'❌ ERROR: Expected "rules" to be a JSON array in {path}, got {type(rules).__name__}')
            sys.exit(1)

        merged.extend(rules)
        print(f"📥 Loaded {len(rules)} rule(s) from {path.name}")

    print(f"\n📊 Total rules: {len(merged)} from {len(input_paths)} file(s)")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"rules": merged}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("\n✨ Merge complete!")
    print(f"💾 Saved to: {output_path.absolute()}")


if __name__ == "__main__":
    main()
