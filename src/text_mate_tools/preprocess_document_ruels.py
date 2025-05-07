import time
import traceback
from pathlib import Path
from typing import List, Optional

from llama_index.core.prompts import PromptTemplate
from llama_index.core.schema import Document
from llama_index.readers.file import PDFReader  # type: ignore
from tqdm import tqdm

from text_mate_backend.custom_vlmm import VllmCustom
from text_mate_backend.models.ruel_models import Ruel, RuelsContainer

prompt = PromptTemplate(
    """You are an expert in editorial guidelines. Take the given document and extract all relevant ruels.

Rules documentation:
{rules}

Your task:
1. Extract all ruels from the document.
2. Compress the ruel description so it is easy for you to understand, and fully appliable later.
3. Identify the file name and page number of the source document.
4. Provide an example of the ruel in use.
5. Keep the text in the original language.

Return your findings as structured data according to the specified format.
""",
)

token_limit = 32_000
max_tokens_for_batch = 25_000
pdf_reader = PDFReader()
llm = VllmCustom()
sllm = llm.as_structured_llm(RuelsContainer)

MAX_RETRIES = 1


def process_batch(
    batch: List[Document], batch_index: int, total_batches: int
) -> tuple[Optional[RuelsContainer], Optional[Exception], str]:
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
        json_docs = ",".join(map(lambda x: x.json(), batch))
        response: RuelsContainer = sllm.structured_predict(
            RuelsContainer,
            prompt,
            rules=f"[{json_docs}]",
        )
        return response, None, batch_page_range
    except Exception as e:
        return None, e, batch_page_range


def get_ruels(path: Path) -> RuelsContainer:
    """
    Extract ruels from a PDF document with detailed progress feedback.
    Includes error handling and retry mechanism for batch processing.

    Args:
        path: Path to the PDF document

    Returns:
        RuelsContainer with extracted rules
    """
    print(f"\n📄 Processing document: {path.name}")
    start_time = time.time()

    try:
        documents = pdf_reader.load_data(file=Path(path))
        print(f"   📑 Loaded {len(documents)} pages")
    except Exception as e:
        print(f"   ❌ ERROR loading document {path.name}: {str(e)}")
        traceback.print_exc()
        return RuelsContainer(rules=[])

    # batch the documents to not exceed the max token limit (32000 tokens)
    batches: List[List[Document]] = []
    current_batch: List[Document] = []
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

    ruels: List[Ruel] = []
    failed_batches = 0

    for i, batch in enumerate(tqdm(batches, desc="   🔍 Processing batches", unit="batch")):
        batch_start = time.time()

        # First attempt
        response, exception, batch_page_range = process_batch(batch, i, len(batches))

        # Retry once if there was an error
        if exception is not None:
            last_log = llm.last_log
            print(f"      ⚠️ Error processing batch {i + 1}/{len(batches)} ({batch_page_range}): {str(exception)}")
            print(f"      📝 Last log: {last_log}")
            print(f"      🔄 Retrying batch {i + 1}/{len(batches)}...")

            # Wait a bit before retrying
            time.sleep(2)

            # Second attempt
            response, retry_exception, _ = process_batch(batch, i, len(batches))

            if retry_exception is not None:
                print(f"      ❌ Retry failed for batch {i + 1}/{len(batches)}: {str(retry_exception)}")
                traceback.print_exc()
                failed_batches += 1
                continue
            else:
                print(f"      ✅ Retry successful for batch {i + 1}/{len(batches)}")

        batch_ruels = response.rules
        ruels.extend(batch_ruels)
        batch_time = time.time() - batch_start
        print(f"      ✅ Found {len(batch_ruels)} rules in {batch_time:.2f}s")

    total_time = time.time() - start_time

    if failed_batches > 0:
        print(f"   ⚠️ {failed_batches} out of {len(batches)} batches failed after retries")

    print(f"   📊 Completed {path.name}: {len(ruels)} rules extracted in {total_time:.2f}s\n")

    return RuelsContainer(rules=ruels)


documents = [
    Path("./docs/empfehlungen-anglizismen-maerz-2020.pdf"),
    Path("./docs/leitfaden_geschlechtergerechte_sprache_3aufl.pdf"),
    Path("./docs/rechtschreibleitfaden-2017.pdf"),
    Path("./docs/schreibweisungen.pdf"),
    Path("./docs/Redaktionsrichtlinien_V6_2024.pdf"),
]

print(f"🚀 Starting rule extraction from {len(documents)} documents")
total_start_time = time.time()
ruels: List[Ruel] = []
failed_documents = []

for i, document in enumerate(documents):
    try:
        print(f"\n[{i + 1}/{len(documents)}] Processing document: {document.name}")
        response = get_ruels(document)
        document_rules = len(response.rules)
        ruels.extend(response.rules)
        print(f"📝 Added {document_rules} rules from {document.name} (Total: {len(ruels)} rules)")
    except Exception as e:
        print(f"❌ ERROR: Failed to process document {document}: {str(e)}")
        traceback.print_exc()
        failed_documents.append(document.name)

total_time = time.time() - total_start_time

# save the ruels to a file
ruels_path = Path("./docs/ruels.json")
ruels_path.write_text(RuelsContainer(rules=ruels).model_dump_json(indent=2))

print(f"\n✨ Process complete!")
print(f"📊 Total rules extracted: {len(ruels)}")
print(f"⏱️ Total processing time: {total_time:.2f}s")
print(f"💾 Rules saved to {ruels_path.absolute()}")

if failed_documents:
    print(f"\n⚠️ Warning: Failed to process {len(failed_documents)} documents:")
    for doc in failed_documents:
        print(f"   - {doc}")
