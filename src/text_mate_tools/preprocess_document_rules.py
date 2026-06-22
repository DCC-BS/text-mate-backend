"""
This script extracts editorial rules from PDF documents using an AI agent.

PDF documents are converted to text via Docling-serve (http://localhost:5001).

Usage:
    uv run --env-file .env src/text_mate_tools/preprocess_document_rules.py <pdf_file> [<pdf_file> ...] --collection <name> [--output OUTPUT_DIR]

Example:
    uv run --env-file .env src/text_mate_tools/preprocess_document_rules.py assets/docs/schreibweisungen.pdf --collection bundeskanzlei
    uv run --env-file .env src/text_mate_tools/preprocess_document_rules.py assets/docs/merkblatt_behoerdenbriefe.pdf --collection merkblatt_behoerdenbriefe

Environment:
    DOCLING_URL       Docling-serve base URL (default: http://localhost:5001/v1)
    DOCLING_API_KEY   Bearer token for Docling (default: none)
    LLM_API_KEY       API key for the LLM
    LLM_URL           LLM endpoint URL
    LLM_MODEL         LLM model name

The script will:
1. Convert PDF documents to markdown via Docling-serve (page-level split)
2. Split pages into batches to manage token limits
3. Use an AI agent to extract rules from each batch
4. Save extracted rules to JSON files in the specified output directory

Output:
    For each input PDF, a corresponding JSON file is created in the output directory
    containing the extracted rules in a structured format. Review this staging output
    and merge rules into the appropriate collection file under assets/docs/rules/.
"""  # noqa: E501

import argparse
import asyncio
import sys
import time
import traceback
from pathlib import Path

import httpx
from dcc_backend_common.llm_agent import BaseAgent
from llama_index.core.schema import Document
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from tqdm import tqdm

from text_mate_backend.models.rule_models import Rule, RulesContainer
from text_mate_backend.utils.configuration import Configuration

prompt = """Du bist ein Experte für Redaktionsrichtlinien. Extrahiere alle Regeln aus dem \
nachstehenden Dokument und gib sie als strukturierte Daten zurück.

## Dokument
{rules}

## Anforderungen an jede Regel

1. **name**: Ein kurzer, eindeutiger, beschreibender Name (max. 80 Zeichen). \
Jeder Regelname muss sich klar von den anderen abheben, damit er von einem LLM \
eindeutig zitiert werden kann.

2. **description**: Eine präzise Beschreibung der Regel (50–400 Zeichen). \
Beschreibe **explizit**, was einen Verstoss gegen diese Regel darstellt. \
Ein Verstoss muss anhand des Textes objektiv feststellbar sein – keine \
stilistischen Vorlieben oder Deutungsspielräume.

3. **example**: Ein konkretes Beispiel im Format:
   `Falsch: <fehlerhafter Text> | Richtig: <korrigierter Text>`
   Das Beispiel muss den Verstoss und die Korrektur klar zeigen.

4. **file_name**: Der Dateiname des Quelldokuments (PDF).

5. **page_number**: Die Seitenzahl, auf der die Regel im Quelldokument steht.

6. **collection**: Setze dieses Feld immer auf "{collection}".

## Wichtige Hinweise
- Verwende Schweizerdeutsch: Schreibe **niemals** «ß», sondern immer «ss».
- Ignoriere Inhaltsverzeichnisse, Register, Kopf- und Fusszeilen und andere \
Nicht-Regel-Inhalte.
- Führe ähnliche Regeln nicht doppelt auf. Wenn sich eine Regel auf mehreren \
Seiten wiederholt, extrahiere sie nur einmal mit der ersten Seitenzahl.
- Behalte die Sprache des Originaldokuments bei.
- Extrahiere **nur** Regeln, die konkret im Text stehen oder sich unmittelbar \
daraus ableiten lassen. Erlfinde keine eigenen Regeln."""

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

token_limit = 8_000
max_tokens_for_batch = 7_000
page_break_placeholder = "\n{{PAGE_BREAK}}\n"


def convert_pdf_with_docling(path: Path, config: Configuration) -> list[Document]:
    """Convert a PDF to page-level Documents via Docling-serve."""
    url = config.docling_url + "/convert/file"
    headers = {"Authorization": f"Bearer {config.docling_api_key}"}

    with open(path, "rb") as f:
        files = {"files": (path.name, f, "application/pdf")}
        data = {
            "to_formats": "md",
            "do_ocr": "true",
            "ocr_lang": ["de", "en", "fr", "it"],
            "md_page_break_placeholder": page_break_placeholder,
        }
        print(f"   📤 Converting {path.name} via Docling ({config.docling_url})...")
        response = httpx.post(url, headers=headers, files=files, data=data, timeout=300.0)

    response.raise_for_status()
    result = response.json()
    md_content = result.get("document", {}).get("md_content", "")

    if not md_content:
        print(f"   ⚠️ Docling returned empty content for {path.name}")
        return []

    pages = md_content.split(page_break_placeholder)
    documents: list[Document] = []
    for i, page_text in enumerate(pages, 1):
        page_text = page_text.strip()
        if page_text:
            documents.append(Document(text=page_text, metadata={"page_label": str(i)}))

    return documents


class PreprocessAgent(BaseAgent[list[Document], RulesContainer]):
    def __init__(self, config: Configuration, collection: str):
        self.collection = collection
        super().__init__(
            config,
            deps_type=list[Document],
            output_type=RulesContainer,
            enable_thinking=True,
        )

    def create_agent(self, model: Model) -> Agent[list[Document], RulesContainer]:
        agent = Agent(model, deps_type=list[Document], output_type=RulesContainer)
        collection = self.collection

        @agent.instructions
        def instructions(ctx: RunContext[list[Document]]) -> str:
            json_docs = ",".join(map(lambda x: x.json(), ctx.deps))
            return prompt.format(rules=f"[{json_docs}]", collection=collection)

        return agent


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


SHORT_DESC_THRESHOLD = 50
LONG_DESC_THRESHOLD = 400


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


async def consolidate_rules(rules: list[Rule], agent: ConsolidationAgent) -> list[Rule]:
    if len(rules) < 2:
        return rules

    print(f"   🔀 Consolidating {len(rules)} rules...")

    before_names = {r.name for r in rules}

    try:
        response = await agent.run(deps=RulesContainer(rules=rules))
        consolidated = response.rules
    except Exception as e:
        print(f"   ⚠️ Consolidation failed: {e}. Keeping unconsolidated rules.")
        return rules

    after_names = {r.name for r in consolidated}
    removed = sorted(before_names - after_names)
    added = sorted(after_names - before_names)

    for name in removed:
        print(f'      ➖ Removed/merged: "{name}"')
    for name in added:
        print(f'      ➕ New: "{name}"')

    print(f"   ✅ Consolidated {len(rules)} → {len(consolidated)} rules")
    return consolidated


async def process_batch(
    batch: list[Document], batch_index: int, total_batches: int, agent: PreprocessAgent
) -> tuple[RulesContainer | None, Exception | None, str]:
    batch_page_range = f"pages {batch[0].metadata.get('page_label', '?')}-{batch[-1].metadata.get('page_label', '?')}"
    print(f"      ⚙️ Processing batch {batch_index + 1}/{total_batches} ({batch_page_range})")

    try:
        response = await agent.run(deps=batch)
        return response, None, batch_page_range
    except Exception as e:
        return None, e, batch_page_range


async def get_rules(
    path: Path, agent: PreprocessAgent, config: Configuration, consolidation_agent: ConsolidationAgent
) -> RulesContainer:
    print(f"\n📄 Processing document: {path.name}")
    start_time = time.time()

    try:
        documents = convert_pdf_with_docling(path, config)
        print(f"   📑 Loaded {len(documents)} pages via Docling")
    except Exception as e:
        print(f"   ❌ ERROR converting document {path.name}: {str(e)}")
        traceback.print_exc()
        return RulesContainer(rules=[])

    batches: list[list[Document]] = []
    current_batch: list[Document] = []
    current_batch_size = 0

    for document in documents:
        if len(document.text) > token_limit:
            print(f"   ⚠️ Warning: Document page {document.metadata.get('page_label', '?')} exceeds token limit")
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_batch_size = 0
            batches.append([document])
            continue

        if current_batch_size + len(document.json()) > max_tokens_for_batch:
            batches.append(current_batch)
            current_batch = []
            current_batch_size = 0

        current_batch.append(document)
        current_batch_size += len(document.json())

    if current_batch:
        batches.append(current_batch)

    print(f"   📦 Created {len(batches)} batches")

    rules: list[Rule] = []
    failed_batches = 0

    for i, batch in enumerate(tqdm(batches, desc="   🔍 Processing batches", unit="batch")):
        batch_start = time.time()

        response, exception, batch_page_range = await process_batch(batch, i, len(batches), agent)

        if exception is not None:
            print(f"      ⚠️ Error processing batch {i + 1}/{len(batches)} ({batch_page_range}): {str(exception)}")
            print(f"      🔄 Retrying batch {i + 1}/{len(batches)}...")
            time.sleep(2)

            response, retry_exception, _ = await process_batch(batch, i, len(batches), agent)

            if retry_exception is not None:
                print(f"      ❌ Retry failed for batch {i + 1}/{len(batches)}: {str(retry_exception)}")
                traceback.print_exc()
                failed_batches += 1
                continue
            else:
                print(f"      ✅ Retry successful for batch {i + 1}/{len(batches)}")

        if response is not None:
            batch_rules = response.rules
            rules.extend(batch_rules)
            batch_time = time.time() - batch_start
            print(f"      ✅ Found {len(batch_rules)} rules in {batch_time:.2f}s")
        else:
            print("      ❌ No rules extracted from batch")

    total_time = time.time() - start_time

    if failed_batches > 0:
        print(f"   ⚠️ {failed_batches} out of {len(batches)} batches failed after retries")

    rules, removed = deduplicate_rules(rules)
    if removed > 0:
        print(f"   🔄 Removed {removed} duplicate rule(s)")

    rules = await consolidate_rules(rules, consolidation_agent)

    rules, removed = deduplicate_rules(rules)
    if removed > 0:
        print(f"   🔄 Removed {removed} duplicate rule(s)")

    print_quality_report(rules, path.name)
    print(f"   📊 Completed {path.name}: {len(rules)} rules extracted in {total_time:.2f}s\n")

    return RulesContainer(rules=rules)


async def main():
    parser = argparse.ArgumentParser(description="Extract rules from PDF documents and save to staging JSON files.")
    parser.add_argument(
        "documents",
        nargs="+",
        type=str,
        help="Path(s) to PDF document(s) to process",
    )
    parser.add_argument(
        "--collection",
        type=str,
        required=True,
        help=(
            "Collection identifier to assign to all extracted rules. "
            "Must match the 'id' field of an entry in assets/docs/meta/bund_dokumente.json "
            "(e.g. 'bundeskanzlei' or 'merkblatt_behoerdenbriefe')."
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./staging/rules",
        help="Output directory for extracted rules JSON files (default: ./staging/rules)",
    )
    args = parser.parse_args()

    document_paths: list[Path] = []
    for doc_path in args.documents:
        path = Path(doc_path)
        if not path.exists():
            print(f"❌ ERROR: Document not found: {doc_path}")
            sys.exit(1)
        if not path.is_file() or path.suffix.lower() != ".pdf":
            print(f"❌ ERROR: Not a PDF file: {doc_path}")
            sys.exit(1)
        document_paths.append(path)

    config = Configuration.from_env()
    agent = PreprocessAgent(config, collection=args.collection)
    consolidation_agent = ConsolidationAgent(config)

    print(f"🚀 Starting rule extraction from {len(document_paths)} document(s)")
    print(f"📌 Collection: {args.collection}")
    print(f"🔗 Docling URL: {config.docling_url}")
    total_start_time = time.time()

    rules_dir = Path(args.output)
    rules_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Staging directory: {rules_dir.absolute()}")

    documents_processed = 0
    total_rules_saved = 0
    failed_documents: list[str] = []

    for i, document in enumerate(document_paths):
        try:
            print(f"\n[{i + 1}/{len(document_paths)}] Processing document: {document.name}")
            response = await get_rules(document, agent, config, consolidation_agent)

            output_filename = document.stem + ".json"
            output_path = rules_dir / output_filename

            output_path.write_text(data=response.model_dump_json(indent=2))

            documents_processed += 1
            total_rules_saved += len(response.rules)
            print(f"💾 Saved {len(response.rules)} rules to {output_path}")
        except Exception as e:
            print(f"❌ ERROR: Failed to process document {document}: {str(e)}")
            traceback.print_exc()
            failed_documents.append(document.name)

    total_time = time.time() - total_start_time

    print("\n✨ Extraction complete!")
    print(f"📊 Documents processed: {documents_processed}/{len(document_paths)}")
    print(f"📊 Total rules extracted: {total_rules_saved}")
    print(f"⏱️ Total processing time: {total_time:.2f}s")
    print(f"💾 Staging directory: {rules_dir.absolute()}")
    print("\n👉 Next steps:")
    print(f"   1. Review the extracted rules in {rules_dir.absolute()}")
    print(f"   2. Merge rules into assets/docs/rules/{args.collection}.json")
    print("   3. Run: uv run python src/text_mate_tools/analyse_rules.py")
    print("   4. Run 'make check' to verify the changes")

    if failed_documents:
        print(f"\n⚠️ Warning: Failed to process {len(failed_documents)} documents:")
        for doc in failed_documents:
            print(f"   - {doc}")


if __name__ == "__main__":
    asyncio.run(main())
