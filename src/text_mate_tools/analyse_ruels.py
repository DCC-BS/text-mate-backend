from pathlib import Path

from text_mate_backend.models.rule_models import RulesContainer

rules_dir = Path("./assets/docs/rules")

all_rules_containers = [
    RulesContainer.model_validate_json(f.read_text())
    for f in sorted(rules_dir.glob("*.json"))
]

all_rules = [rule for container in all_rules_containers for rule in container.rules]

n_rules = len(all_rules)

collections_rule_count: dict[str, int] = {}
collections_char_count: dict[str, int] = {}

for rule in all_rules:
    collections_rule_count.setdefault(rule.collection, 0)
    collections_char_count.setdefault(rule.collection, 0)
    collections_rule_count[rule.collection] += 1
    collections_char_count[rule.collection] += len(rule.model_dump_json())

print(f"Total rules: {n_rules}")

for collection, count in sorted(collections_rule_count.items()):
    print(f"Collection: {collection} — Rules: {count}, Characters: {collections_char_count[collection]}")

print(f"Total collections: {len(collections_rule_count)}")
