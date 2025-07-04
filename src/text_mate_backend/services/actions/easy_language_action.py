from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate

from text_mate_backend.services.actions.action_utils import PromptOptions, run_prompt
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.easy_language import CLAUDE_TEMPLATE_ES, REWRITE_COMPLETE, RULES_ES, SYSTEM_MESSAGE_ES


def easy_language(text: str, llm_facade: LLMFacade) -> StreamingResponse:
    prompt = PromptTemplate(SYSTEM_MESSAGE_ES + CLAUDE_TEMPLATE_ES).format(
        prompt=text, completeness=REWRITE_COMPLETE, rules=RULES_ES
    )

    options: PromptOptions = PromptOptions(prompt=prompt)

    return run_prompt(
        options,
        llm_facade,
    )
