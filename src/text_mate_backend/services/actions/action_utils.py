from fastapi.responses import StreamingResponse
from openai import BaseModel, OpenAI
from openai.types.chat import ChatCompletionChunk
from typing import Generator, Iterator
from text_mate_backend.utils.configuration import Configuration

config = Configuration()

SYSTEM_PROMPT_POSTFIX: str = (
    "Format the text as plain text, don't use any html tags or markdwon."
    "Answer in the same language as the input text."
    "Only respond with the answer, do not add any other text."
)

# SYSTEM_PROMPT_POSTFIX = (
#     "Format the text as html, using <p> tags for paragraphs and <br> tags for line breaks."
#     "Use <strong> for bold text."
#     "Use <ul> and <li> for lists."
#     "Do not use any other tags."
#     "Answer in the same language as the input text."
#     "Only respond with the html code, do not add any other text."
# )


class PrompOptions(BaseModel):
    """
    A class to represent the options for a prompt.
    """

    system_prompt: str
    user_prompt: str
    temperature: float = 0.7


def run_prompt(options: PrompOptions, llm: OpenAI) -> StreamingResponse:
    """
    Runs the given prompt using the OpenAI API and returns a streaming response.

    Args:
        options: The prompt options including system prompt, user prompt and temperature
        llm: The OpenAI client instance to use for generating the response

    Returns:
        A StreamingResponse that yields the generated text chunks
    """

    stream: Iterator[ChatCompletionChunk] = llm.chat.completions.create(
        model=config.llm_model,
        messages=[
            {"role": "system", "content": f"{options.system_prompt} {SYSTEM_PROMPT_POSTFIX}"},
            {"role": "user", "content": options.user_prompt},
        ],
        stream=True,
        temperature=options.temperature,
    )

    def generate() -> Generator[str, None, None]:
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content.replace("ß", "ss")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
