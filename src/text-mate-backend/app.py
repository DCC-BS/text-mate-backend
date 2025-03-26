from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from functional_monads.either import Either
from models.text_corretion_models import CorrectionResult, TextCorrectionOptions
from models.text_rewrite_models import RewriteResult, TextRewriteOptions
from pydantic import BaseModel
from services.advisor import AdvisorOutput, AdvisorService
from services.rewrite_text import TextRewriteService
from services.text_correction_language_tool import TextCorrectionService
from utils.configuration import config
from utils.logger import get_logger, init_logger

init_logger()

app = FastAPI()
logger = get_logger()

logger.info(f"Running with configuration: {config}")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.client_url],  # Nuxt.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

text_correction_service = TextCorrectionService()
text_rewrite_service = TextRewriteService()
advisor_service = AdvisorService()


def handle_result[T](result: Either[str, T]) -> T:
    def handle_error(error: str) -> Any:
        raise HTTPException(status_code=400, detail=error)

    return result.fold(  # type: ignore
        handle_error,
        lambda value: value,
    )


class CorrectionInput(BaseModel):
    text: str


@app.post("/text-correction")
def chat_completions(text: CorrectionInput) -> CorrectionResult:
    result = text_correction_service.correct_text(text.text, TextCorrectionOptions())
    return handle_result(result)


class RewriteInput(BaseModel):
    text: str
    context: str
    domain: str = "general"
    formality: str = "neutral"


@app.post("/text-rewrite")
def rewrite_text(data: RewriteInput) -> RewriteResult:
    options = TextRewriteOptions(domain=data.domain, formality=data.formality)

    result: Either[str, RewriteResult] = text_rewrite_service.rewrite_text(data.text, data.context, options)
    return handle_result(result)


class AdvisorInput(BaseModel):
    text: str
    domain: str = "general"
    formality: str = "neutral"


@app.post("/advisor")
def advisor(data: AdvisorInput) -> AdvisorOutput:
    options = TextRewriteOptions(domain=data.domain, formality=data.formality)

    result = advisor_service.advise_changes(data.text, options)
    return handle_result(result)
