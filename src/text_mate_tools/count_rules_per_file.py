import argparse
import json
from collections import Counter
from pathlib import Path


def get_default_rules_path() -> Path:
    """
    Returns the default path to docs/rules.json assuming the following layout:

    text-mate-backend/
      docs/rules.json
      src/...
    """
    # This file is expected at: <repo_root>/src/text_mate_tools/count_rules_per_file.py
    # So repo_root is two levels up.
    return Path(__file__).resolve().parents[2] / "docs" / "rules.json"


def count_rules_per_file(rules_path: Path) -> Counter[str]:
    with rules_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rules = data.get("rules", [])
    counter: Counter[str] = Counter()

    for rule in rules:
        file_name = rule.get("file_name")
        if file_name:
            counter[file_name] += 1

    return counter


def main() -> None:
    parser = argparse.ArgumentParser(description="Count how many rules each file_name has in docs/rules.json.")
    parser.add_argument(
        "--rules-path",
        type=str,
        default=str(get_default_rules_path()),
        help="Path to rules.json (default: <repo_root>/docs/rules.json)",
    )
    args = parser.parse_args()

    rules_path = Path(args.rules_path).expanduser().resolve()

    if not rules_path.is_file():
        raise SystemExit(f"File not found at: {rules_path}")

    counts = count_rules_per_file(rules_path)

    # Print sorted by file_name for stable output
    print(f"Counts per file_name in {rules_path}:")
    for file_name in sorted(counts.keys()):
        print(f"{file_name}: {counts[file_name]}")


if __name__ == "__main__":
    main()
