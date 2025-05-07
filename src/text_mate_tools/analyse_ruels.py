from pathlib import Path

from text_mate_backend.models.ruel_models import RuelsContainer

ruels_file = Path("./docs/ruels.json")

ruels_container = RuelsContainer.model_validate_json(
    ruels_file.read_text(),
    strict=True,
)

n_ruels = len(ruels_container.rules)

documents_stats = {}

for ruel in ruels_container.rules:
    if ruel.file_name not in documents_stats:
        documents_stats[ruel.file_name] = 0

    documents_stats[ruel.file_name] += 1

print(f"Total ruels: {n_ruels}")

for file_name, n_ruels in documents_stats.items():
    print(f"File: {file_name} - Ruels: {n_ruels}")

print(f"Total files: {len(documents_stats)}")
