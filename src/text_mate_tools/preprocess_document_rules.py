"""
This script extracts editorial rules from PDF documents using an AI agent.

Usage:
    uv run --env-file .env src/text_mate_tools/preprocess_document_rules.py <pdf_file> [<pdf_file> ...] --collection <name> [--output OUTPUT_DIR]

Example:
    uv run --env-file .env src/text_mate_tools/preprocess_document_rules.py assets/docs/schreibweisungen.pdf --collection bundeskanzlei
    uv run --env-file .env src/text_mate_tools/preprocess_document_rules.py assets/docs/merkblatt_behoerdenbriefe.pdf --collection merkblatt_behoerdenbriefe

The script will:
1. Load and parse PDF documents
2. Split documents into batches to manage token limits
3. Use an AI agent to extract rules from each batch
4. Save extracted rules to JSON files in the specified output directory

Output:
    For each input PDF, a corresponding JSON file is created in the output directory
    containing the extracted rules in a structured format. Review this staging output
    and merge rules into the appropriate collection file under assets/docs/rules/.

Requirements:
    - PDF documents to process must exist and be readable
    - Environment must be configured with proper API keys (loaded from .env)
    - Output directory will be created if it doesn't exist (default: ./staging/rules/)
"""  # noqa: E501

import argparse
import asyncio
import sys
import time
import traceback
from pathlib import Path

from dcc_backend_common.llm_agent import BaseAgent
from llama_index.core.schema import Document
from llama_index.readers.file import PDFReader  # type: ignore
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.tools import RunContext
from tqdm import tqdm

from text_mate_backend.models.rule_models import Rule, RulesContainer
from text_mate_backend.utils.configuration import Configuration

prompt = """You are an expert in editorial guidelines. Take the given document and extract all relevant rules.

Rules documentation:
{rules}

Your task:
1. Extract all rules from the document.
2. Identify the file name and page number of the source document for each rule.
3. Set the `collection` field to "{collection}" for every rule.
4. Provide an example of the rule in use.
5. Keep the text in the original language.
6. Ignore indexes, tables of contents, and other non-relevant content.

Return your findings as structured data according to the specified format.
"""

token_limit = 8_000
max_tokens_for_batch = 7_000
pdf_reader = PDFReader()


class PreprocessAgent(BaseAgent[list[Document], RulesContainer]):
    def __init__(self, config: Configuration, collection: str):
        self.collection = collection
        super().__init__(config, deps_type=list[Document], output_type=RulesContainer)

    def create_agent(self, model: Model) -> Agent[list[Document], RulesContainer]:
        agent = Agent(model, deps_type=list[Document], output_type=RulesContainer)
        collection = self.collection

        @agent.instructions
        def instructions(ctx: RunContext[list[Document]]) -> str:
            json_docs = ",".join(map(lambda x: x.json(), ctx.deps))
            return prompt.format(rules=f"[{json_docs}]", collection=collection)

        return agent


MAX_RETRIES = 1


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


async def get_rules(path: Path, agent: PreprocessAgent) -> RulesContainer:
    print(f"\n📄 Processing document: {path.name}")
    start_time = time.time()

    try:
        documents = pdf_reader.load_data(file=Path(path))
        print(f"   📑 Loaded {len(documents)} pages")
    except Exception as e:
        print(f"   ❌ ERROR loading document {path.name}: {str(e)}")
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

    agent = PreprocessAgent(Configuration.from_env(), collection=args.collection)

    print(f"🚀 Starting rule extraction from {len(document_paths)} document(s)")
    print(f"📌 Collection: {args.collection}")
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
            response = await get_rules(document, agent)

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
    print("   2. Remove duplicates and refine rule descriptions")
    print(f"   3. Merge rules into assets/docs/rules/{args.collection}.json")
    print("   4. Run 'make check' to verify the changes")

    if failed_documents:
        print(f"\n⚠️ Warning: Failed to process {len(failed_documents)} documents:")
        for doc in failed_documents:
            print(f"   - {doc}")


if __name__ == "__main__":
    asyncio.run(main())
