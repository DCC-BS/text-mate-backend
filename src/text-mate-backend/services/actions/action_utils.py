from fastapi.responses import StreamingResponse
from openai import BaseModel, OpenAI
from utils.configuration import config

SYSTEM_PROMPT_POSTFIX = (
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
    """

    stream = llm.chat.completions.create(
        model=config.llm_model,
        messages=[
            {"role": "system", "content": f"{options.system_prompt} {SYSTEM_PROMPT_POSTFIX}"},
            {"role": "user", "content": options.user_prompt},
        ],
        stream=True,
        temperature=options.temperature,
    )

    def generate():
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content.replace("ß", "ss")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
