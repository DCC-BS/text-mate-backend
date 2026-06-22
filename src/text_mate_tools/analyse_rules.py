import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from text_mate_backend.models.rule_models import Rule, RulesContainer
from text_mate_backend.services.advisor import MAX_RULES_PER_REQUEST

RULES_DIR = Path("assets/docs/rules")

SHORT_DESC_THRESHOLD = 50
LONG_DESC_THRESHOLD = 500
SIMILAR_NAME_THRESHOLD = 0.8


def load_rules() -> list[Rule]:
    containers = [RulesContainer.model_validate_json(f.read_text()) for f in sorted(RULES_DIR.glob("*.json"))]
    return [rule for container in containers for rule in container.rules]


def approximate_tokens(text: str) -> int:
    return len(text) // 4


def check_duplicate_names(rules: list[Rule]) -> list[tuple[str, list[str]]]:
    name_to_collections: dict[str, list[str]] = defaultdict(list)
    for rule in rules:
        name_to_collections[rule.name].append(rule.collection)
    return [(name, cols) for name, cols in name_to_collections.items() if len(cols) > 1]


def check_similar_names(rules: list[Rule]) -> list[tuple[str, str, float]]:
    pairs: list[tuple[str, str, float]] = []
    for i, a in enumerate(rules):
        for b in rules[i + 1 :]:
            ratio = SequenceMatcher(None, a.name.lower(), b.name.lower()).ratio()
            if ratio >= SIMILAR_NAME_THRESHOLD and a.name != b.name:
                pairs.append((a.name, b.name, ratio))
    return pairs


def check_descriptions(rules: list[Rule]) -> tuple[list[Rule], list[Rule]]:
    short = [r for r in rules if len(r.description) < SHORT_DESC_THRESHOLD]
    long_ = [r for r in rules if len(r.description) > LONG_DESC_THRESHOLD]
    return short, long_


def check_examples(rules: list[Rule]) -> list[Rule]:
    weak: list[Rule] = []
    for r in rules:
        ex = r.example.strip()
        if not ex or "falsch" not in ex.lower() or "richtig" not in ex.lower():
            weak.append(r)
    return weak


def check_eszett(rules: list[Rule]) -> list[Rule]:
    return [r for r in rules if "ß" in r.name or "ß" in r.description or "ß" in r.example]


def check_collection_files(rules: list[Rule]) -> list[tuple[str, set[str]]]:
    collection_files: dict[str, set[str]] = defaultdict(set)
    for r in rules:
        collection_files[r.collection].add(r.file_name)
    return [(col, files) for col, files in collection_files.items() if len(files) > 1]


def simulate_batches(rules: list[Rule]) -> list[list[Rule]]:
    sorted_rules = sorted(rules, key=lambda r: r.collection)
    batches: list[list[Rule]] = []
    for i in range(0, len(sorted_rules), MAX_RULES_PER_REQUEST):
        batches.append(sorted_rules[i : i + MAX_RULES_PER_REQUEST])
    return batches


def print_summary(rules: list[Rule]) -> None:
    collections = sorted({r.collection for r in rules})
    print("=" * 80)
    print(" RULE SUMMARY")
    print("=" * 80)
    print(f"  Total rules:       {len(rules)}")
    print(f"  Collections:       {len(collections)}")
    print(f"  Batch size:        {MAX_RULES_PER_REQUEST}")
    print(f"  Total batches:     {(len(rules) + MAX_RULES_PER_REQUEST - 1) // MAX_RULES_PER_REQUEST}")
    print(f"  Approx. tokens:    {sum(approximate_tokens(r.model_dump_json()) for r in rules)}")
    print()


def print_collection_table(rules: list[Rule]) -> None:
    collections = sorted({r.collection for r in rules})
    print("-" * 80)
    print(" COLLECTIONS")
    print("-" * 80)
    print(f"  {'Collection':<35} {'Rules':>5}  {'Avg desc':>8}  {'Min':>4}  {'Max':>4}  {'Files':>5}")
    print(f"  {'-' * 35} {'-' * 5}  {'-' * 8}  {'-' * 4}  {'-' * 4}  {'-' * 5}")
    for col in collections:
        col_rules = [r for r in rules if r.collection == col]
        desc_lens = [len(r.description) for r in col_rules]
        files = {r.file_name for r in col_rules}
        avg = sum(desc_lens) // len(desc_lens) if desc_lens else 0
        print(f"  {col:<35} {len(col_rules):>5}  {avg:>8}  {min(desc_lens):>4}  {max(desc_lens):>4}  {len(files):>5}")
    print()


def print_batches(batches: list[list[Rule]]) -> None:
    print("-" * 80)
    print(" BATCH SIMULATION (sorted by collection)")
    print("-" * 80)
    for i, batch in enumerate(batches, 1):
        cols = sorted({r.collection for r in batch})
        tokens = sum(approximate_tokens(r.model_dump_json()) for r in batch)
        print(f"  Batch {i}: collections={', '.join(cols)}  ~{tokens} tokens  ({len(batch)} rules)")
        for r in batch:
            print(f"    - {r.name}")
    print()


def print_warnings(
    duplicates: list[tuple[str, list[str]]],
    similar: list[tuple[str, str, float]],
    short: list[Rule],
    long_: list[Rule],
    weak_examples: list[Rule],
    eszett: list[Rule],
    col_files: list[tuple[str, set[str]]],
) -> bool:
    has_critical = False
    print("=" * 80)
    print(" QUALITY WARNINGS")
    print("=" * 80)

    if duplicates:
        has_critical = True
        print(f"\n  [DUPLICATE_NAME] {len(duplicates)} duplicate rule name(s) — breaks rule_lookup:")
        for name, cols in duplicates:
            print(f"    '{name}' in collections: {', '.join(cols)}")

    if similar:
        print(f"\n  [SIMILAR_NAME] {len(similar)} similar rule name pair(s) — LLM confusion risk:")
        for a, b, ratio in sorted(similar, key=lambda x: -x[2]):
            print(f"    {ratio:.0%}  '{a}'  <->  '{b}'")

    if short:
        print(f"\n  [SHORT_DESCRIPTION] {len(short)} rule(s) with description < {SHORT_DESC_THRESHOLD} chars:")
        for r in short:
            print(f"    [{r.collection}] {r.name}  ({len(r.description)} chars)")

    if long_:
        print(f"\n  [LONG_DESCRIPTION] {len(long_)} rule(s) with description > {LONG_DESC_THRESHOLD} chars:")
        for r in long_:
            print(f"    [{r.collection}] {r.name}  ({len(r.description)} chars)")

    if weak_examples:
        print(f"\n  [WEAK_EXAMPLE] {len(weak_examples)} rule(s) with missing 'Falsch:'/'Richtig:' pattern:")
        for r in weak_examples:
            preview = r.example[:60] + "..." if len(r.example) > 60 else r.example or "(empty)"
            print(f"    [{r.collection}] {r.name}  -> {preview}")

    if eszett:
        print(f"\n  [ESZETT_IN_RULES] {len(eszett)} rule(s) containing 'ß' — postprocessors disabled for advisor:")
        for r in eszett:
            print(f"    [{r.collection}] {r.name}")

    if col_files:
        print(f"\n  [COLLECTION_MISMATCH] {len(col_files)} collection(s) with multiple file_names:")
        for col, files in col_files:
            print(f"    {col}: {', '.join(sorted(files))}")

    if not any([duplicates, similar, short, long_, weak_examples, eszett, col_files]):
        print("\n  No warnings. All rules look good.")

    print()
    return has_critical


def main() -> None:
    rules = load_rules()

    print_summary(rules)
    print_collection_table(rules)

    batches = simulate_batches(rules)
    print_batches(batches)

    duplicates = check_duplicate_names(rules)
    similar = check_similar_names(rules)
    short, long_ = check_descriptions(rules)
    weak_examples = check_examples(rules)
    eszett = check_eszett(rules)
    col_files = check_collection_files(rules)

    has_critical = print_warnings(duplicates, similar, short, long_, weak_examples, eszett, col_files)

    if has_critical:
        print("CRITICAL: Duplicate rule names found. Fix before using with advisor.")
        sys.exit(1)


if __name__ == "__main__":
    main()
