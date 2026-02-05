"""
This script extracts editorial rules from PDF documents using an AI agent.

Usage:
    uv run --env-file .env src/text_mate_tools/preprocess_document_rules.py <pdf_file> [<pdf_file> ...] [--output OUTPUT_DIR]

Example:
    uv run --env-file .env src/text_mate_tools/preprocess_document_rules.py docs/*.pdf --output ./output/rules

The script will:
1. Load and parse PDF documents
2. Split documents into batches to manage token limits
3. Use an AI agent to extract rules from each batch
4. Save extracted rules to JSON files in the specified output directory

Output:
    For each input PDF, a corresponding JSON file is created in the output directory
    containing the extracted rules in a structured format.

Requirements:
    - PDF documents to process must exist and be readable
    - Environment must be configured with proper API keys (loaded from .env)
    - Output directory will be created if it doesn't exist (default: ./docs/rules/)
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
2. Identify the file name and page number of the document json.
3. Provide an example of the ruel in use.
4. Keep the text in the original language.
5. Ignore Indexes, tables of contents, and other non-relevant content.

Return your findings as structured data according to the specified format.
"""

token_limit = 8_000
max_tokens_for_batch = 7_000
pdf_reader = PDFReader()


class PreprocessAgent(BaseAgent[list[Document], RulesContainer]):
    def __init__(self, config: Configuration):
        super().__init__(config, deps_type=list[Document], output_type=RulesContainer)

    def create_agent(self, model: Model) -> Agent[list[Document], RulesContainer]:
        agent = Agent(model, deps_type=list[Document], output_type=RulesContainer)

        @agent.instructions
        def instructions(ctx: RunContext[list[Document]]) -> str:
            json_docs = ",".join(map(lambda x: x.json(), ctx.deps))
            return prompt.format(rules=f"[{json_docs}]")

        return agent


agent = PreprocessAgent(Configuration.from_env())

MAX_RETRIES = 1


async def process_batch(
    batch: list[Document], batch_index: int, total_batches: int
) -> tuple[RulesContainer | None, Exception | None, str]:
    """
    Process a batch of documents and extract rules with error handling.

    Args:
        batch: List of documents to process
        batch_index: Index of the current batch
        total_batches: Total number of batches

    Returns:
        Tuple containing (response or None, exception or None, batch_page_range)
    """
    batch_page_range = f"pages {batch[0].metadata.get('page_label', '?')}-{batch[-1].metadata.get('page_label', '?')}"
    print(f"      ⚙️ Processing batch {batch_index + 1}/{total_batches} ({batch_page_range})")

    try:
        response = await agent.run(deps=batch)

        return response, None, batch_page_range
    except Exception as e:
        return None, e, batch_page_range


async def get_rules(path: Path) -> RulesContainer:
    """
    Extract rules from a PDF document with detailed progress feedback.
    Includes error handling and retry mechanism for batch processing.

    Args:
        path: Path to the PDF document

    Returns:
            Container with extracted rules
    """
    print(f"\n📄 Processing document: {path.name}")
    start_time = time.time()

    try:
        documents = pdf_reader.load_data(file=Path(path))
        print(f"   📑 Loaded {len(documents)} pages")
    except Exception as e:
        print(f"   ❌ ERROR loading document {path.name}: {str(e)}")
        traceback.print_exc()
        return RulesContainer(rules=[])

    # batch the documents to not exceed the max token limit (32000 tokens)
    batches: list[list[Document]] = []
    current_batch: list[Document] = []
    current_batch_size = 0

    for document in documents:
        if len(document.text) > token_limit:
            print(f"   ⚠️ Warning: Document page {document.metadata.get('page_label', '?')} exceeds token limit")
            # Try to process it anyway by making it a separate batch
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

    # Add the last batch if it's not empty
    if current_batch:
        batches.append(current_batch)

    print(f"   📦 Created {len(batches)} batches")

    rules: list[Rule] = []
    failed_batches = 0

    for i, batch in enumerate(tqdm(batches, desc="   🔍 Processing batches", unit="batch")):
        batch_start = time.time()

        # First attempt
        response, exception, batch_page_range = await process_batch(batch, i, len(batches))

        # Retry once if there was an error
        if exception is not None:
            print(f"      ⚠️ Error processing batch {i + 1}/{len(batches)} ({batch_page_range}): {str(exception)}")
            print(f"      🔄 Retrying batch {i + 1}/{len(batches)}...")

            # Wait a bit before retrying
            time.sleep(2)

            # Second attempt
            response, retry_exception, _ = await process_batch(batch, i, len(batches))

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
    parser = argparse.ArgumentParser(
        description="Extract rules from PDF documents and save to JSON files in docs/rules/"
    )
    parser.add_argument(
        "documents",
        nargs="+",
        type=str,
        help="Path(s) to PDF document(s) to process",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./docs/rules",
        help="Output directory for extracted rules JSON files (default: ./docs/rules)",
    )
    args = parser.parse_args()

    # Convert argument paths to Path objects and resolve relative paths
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

    print(f"🚀 Starting rule extraction from {len(document_paths)} document(s)")
    total_start_time = time.time()

    # Create rules directory if it doesn't exist
    rules_dir = Path(args.output)
    rules_dir.mkdir(exist_ok=True)
    print(f"📁 Using rules directory: {rules_dir.absolute()}")

    # Write rules for each document to separate JSON files
    documents_processed = 0
    total_rules_saved = 0
    failed_documents: list[str] = []

    for i, document in enumerate(document_paths):
        try:
            print(f"\n[{i + 1}/{len(document_paths)}] Processing document: {document.name}")
            response = await get_rules(document)

            # Create output file name based on document name
            output_filename = document.stem + ".json"
            output_path = rules_dir / output_filename

            # Write rules to separate file
            output_path.write_text(data=response.model_dump_json(indent=2))

            documents_processed += 1
            total_rules_saved += len(response.rules)
            print(f"💾 Saved {len(response.rules)} rules to {output_path.name}")
        except Exception as e:
            print(f"❌ ERROR: Failed to process document {document}: {str(e)}")
            traceback.print_exc()
            failed_documents.append(document.name)

    total_time = time.time() - total_start_time

    print("\n✨ Process complete!")
    print(f"📊 Documents processed: {documents_processed}/{len(document_paths)}")
    print(f"📊 Total rules saved: {total_rules_saved}")
    print(f"⏱️ Total processing time: {total_time:.2f}s")
    print(f"💾 Rules directory: {rules_dir.absolute()}")

    if failed_documents:
        print(f"\n⚠️ Warning: Failed to process {len(failed_documents)} documents:")
        for doc in failed_documents:
            print(f"   - {doc}")


if __name__ == "__main__":
    asyncio.run(main())
