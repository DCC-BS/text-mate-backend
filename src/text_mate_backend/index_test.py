from pathlib import Path

from llama_index.core.prompts import PromptTemplate
from llama_index.core.schema import Document
from llama_index.readers.file import PDFReader  # type: ignore
from pydantic import BaseModel, Field
from tqdm import tqdm

from text_mate_backend.custom_vlmm import VllmCustom


class Ruel(BaseModel):
    name: str = Field(description="A descriptive name for the rule")
    description: str = Field(description="Description of the rule")
    file_name: str = Field(description="Filename of the source document")
    page_number: int = Field(description="Page number of the source document")
    example: str = Field(description="Example of the rule in use")


class RuelsResponse(BaseModel):
    rules: list[Ruel] = Field(description="All violations of the rules")


prompt = PromptTemplate(
    """You are an expert in editorial guidelines. Take the given document and extract all relevant ruels.

Rules documentation:
{rules}

Your task:
1. Extract all ruels from the document.
2. Compress the ruel description so it is easy for you to understand, and fully appliable later.
3. Identify the file name and page number of the source document.
4. Provide an example of the ruel in use.
5. Keep the text int he original language.

Return your findings as structured data according to the specified format.
""",
)

pdf_reader = PDFReader()
llm = VllmCustom()
sllm = llm.as_structured_llm(RuelsResponse)


def get_ruels(path: Path) -> RuelsResponse:
    documents = pdf_reader.load_data(file=Path(path))

    # batch the documents to not exceet the max token limit (32000 tokens)
    batches: list[list[Document]] = []
    current_batch: list[Document] = []
    current_batch_size = 0

    for document in documents:
        if len(document.text) > 32000:
            raise ValueError("Document is too large to process in one go.")

        if current_batch_size > 25000:
            batches.append(current_batch)
            current_batch = []

        current_batch.append(document)
        current_batch_size += len(document.text)

    ruels: list[Ruel] = []

    for batch in tqdm(batches, desc="Processing batches"):
        json_docs = ",".join(map(lambda x: x.json(), batch))

        response: RuelsResponse = sllm.structured_predict(
            RuelsResponse,
            prompt,
            rules=f"[{json_docs}]",
        )

        ruels.extend(response.rules)

    return RuelsResponse(rules=ruels)


documents = [
    Path("./docs/empfehlungen-anglizismen-maerz-2020.pdf"),
    Path("./docs/leitfaden_geschlechtergerechte_sprache_3aufl.pdf"),
    Path("./docs/rechtschreibleitfaden-2017.pdf"),
    Path("./docs/schreibweisungen.pdf"),
    Path("./docs/Redaktionsrichtlinien_V6_2024.pdf"),
]

ruels = []

for document in tqdm(documents, desc="Processing documents"):
    response = get_ruels(document)
    ruels.extend(response.rules)

# save the ruels to a file
ruels_path = Path("./docs/ruels.json")
ruels_path.write_text(RuelsResponse(rules=ruels).model_dump_json(indent=2))

print(f"Ruels saved to {ruels_path}")
