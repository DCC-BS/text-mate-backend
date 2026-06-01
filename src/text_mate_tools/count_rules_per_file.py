import argparse
from collections import Counter
from pathlib import Path


def get_default_rules_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "docs" / "rules"


def count_rules(rules_dir: Path) -> tuple[Counter[str], Counter[str]]:
    """Returns (rules per collection, rules per source PDF)."""
    per_collection: Counter[str] = Counter()
    per_file: Counter[str] = Counter()

    for json_file in sorted(rules_dir.glob("*.json")):
        import json

        data = json.loads(json_file.read_text())
        for rule in data.get("rules", []):
            collection = rule.get("collection", "<no collection>")
            file_name = rule.get("file_name", "<no file>")
            per_collection[collection] += 1
            per_file[file_name] += 1

    return per_collection, per_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Count rules per collection and source PDF in assets/docs/rules/.")
    parser.add_argument(
        "--rules-dir",
        type=str,
        default=str(get_default_rules_dir()),
        help="Path to rules directory (default: <repo_root>/assets/docs/rules/)",
    )
    args = parser.parse_args()

    rules_dir = Path(args.rules_dir).expanduser().resolve()

    if not rules_dir.is_dir():
        raise SystemExit(f"Directory not found: {rules_dir}")

    per_collection, per_file = count_rules(rules_dir)

    total = sum(per_collection.values())
    print(f"Total rules: {total}\n")

    print("Rules per collection:")
    for collection in sorted(per_collection):
        print(f"  {collection}: {per_collection[collection]}")

    print("\nRules per source PDF:")
    for file_name in sorted(per_file):
        print(f"  {file_name}: {per_file[file_name]}")


if __name__ == "__main__":
    main()
