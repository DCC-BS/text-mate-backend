from pathlib import Path

from text_mate_backend.models.ruel_models import RuelsContainer

ruels_file = Path("./docs/ruels.json")

ruels_container = RuelsContainer.model_validate_json(
    ruels_file.read_text(),
    strict=True,
)

n_ruels = len(ruels_container.rules)

documents_ruel_count = {}
documents_char_count = {}

for ruel in ruels_container.rules:
    if ruel.file_name not in documents_ruel_count:
        documents_ruel_count[ruel.file_name] = 0
        documents_char_count[ruel.file_name] = 0

    documents_ruel_count[ruel.file_name] += 1
    documents_char_count[ruel.file_name] += len(ruel.model_dump_json())

print(f"Total ruels: {n_ruels}")

for file_name, n_ruels in documents_ruel_count.items():
    print(f"File: {file_name} - Ruels: {n_ruels}")
    print(f"File: {file_name} - Characters: {documents_char_count[file_name]}")

print(f"Total files: {len(documents_ruel_count)}")
