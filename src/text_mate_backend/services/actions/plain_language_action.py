from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.easy_language import CLAUDE_TEMPLATE_LS, REWRITE_COMPLETE, RULES_LS, SYSTEM_MESSAGE_LS


def plain_language(text: str, config: Configuration, llm_facade: LLMFacade) -> StreamingResponse:
    prompt = PromptTemplate(SYSTEM_MESSAGE_LS + CLAUDE_TEMPLATE_LS).format(
        prompt=text, completeness=REWRITE_COMPLETE, rules=RULES_LS
    )

    options: PromptOptions = PromptOptions(prompt=prompt, llm_model=config.llm_model)

    return run_prompt(
        options,
        llm_facade,
    )
