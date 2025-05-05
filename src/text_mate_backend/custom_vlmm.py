from typing import Any, List, Mapping, Optional

from llama_index.core import Settings, SimpleDirectoryReader, SummaryIndex
from llama_index.core.callbacks import CallbackManager
from llama_index.core.llms import (
    CompletionResponse,
    CompletionResponseGen,
    CustomLLM,
    LLMMetadata,
)
from llama_index.core.llms.callbacks import llm_completion_callback
from openai import OpenAI
from pydantic import Field

from text_mate_backend.utils.configuration import config


class VllmCustom(CustomLLM):
    client: OpenAI = Field(default=None, description="OpenAI client instance")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_api_base_url,
        )

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(model_name=config.llm_model)

    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        completion = self.client.chat.completions.create(
            model=config.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        print(completion)

        output: str = completion.choices[0].message.content

        print(f"Output: {output}")
        return CompletionResponse(text=output, raw=completion)

    @llm_completion_callback()
    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        response = ""

        stream = self.client.completions.create(
            model=config.llm_model,
            prompt=prompt,
            max_tokens=100,
            temperature=0.1,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content.replace("ß", "ss")
                response += content
                yield CompletionResponse(text=response, delta=content)
