import json
from pathlib import Path

from llama_index.core.prompts import PromptTemplate
from llama_index.llms.openai_like import OpenAILike
from llama_index.readers.file import PDFReader
from pydantic import BaseModel, Field

from text_mate_backend.custom_vlmm import VllmCustom
from text_mate_backend.utils.configuration import config

# from llama_index.readers.file import PDFReader


class Ruel(BaseModel):
    name: str = Field(description="A descriptive name for the rule")
    description: str = Field(description="Description of the rule")
    file_name: str = Field(description="Filename of the source document")
    page_number: int = Field(description="Page number of the source document")


class RuelsResponse(BaseModel):
    rules: list[Ruel] = Field(description="All violations of the rules")


pdf_reader = PDFReader()
documents = pdf_reader.load_data(file=Path("./docs/Redaktionsrichtlinien_V6_2024.pdf"))

prompt = PromptTemplate(
    """You are an expert in editorial guidelines. Review the given text and check for violations of the rules found in the provided documents.

Text to review: {text}

Rules documentation:
{rules}

Your task:
1. Identify any violations of the editorial guidelines in the text
2. For each violation, specify the rule name, description, file name, and page number
3. If no violations are found, return an empty list
4. Answer in the language of the text

Return your findings as structured data according to the specified format.
""",
)

llm = VllmCustom()
# test_response = llm.complete("What is 2+2?")
# print(f"API test response: {test_response.text}")

sllm = llm.as_structured_llm(RuelsResponse)

json_docs = ",".join(map(lambda x: x.json(), documents))

response = sllm.structured_predict(
    RuelsResponse,
    prompt,
    text="Liebe Mitarbeter ich habe eine Frage zu den Redaktionsrichtlinien. Ich habe das Gefühl, dass ich nicht alle Regeln befolgen kann. Was soll ich tun?",
    rules=f"[{json_docs}]",
)

json_output = response.model_dump_json()
print(json.dumps(json.loads(json_output), indent=2))
