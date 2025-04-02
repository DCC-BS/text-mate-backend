from fastapi.responses import StreamingResponse
from openai import BaseModel, OpenAI
from utils.configuration import config


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
            {"role": "system", "content": options.system_prompt},
            {"role": "user", "content": options.user_prompt},
        ],
        stream=True,
        temperature=options.temperature,
    )

    async def generate():
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    return StreamingResponse(
        generate(),
        media_type="text/plain",
    )
