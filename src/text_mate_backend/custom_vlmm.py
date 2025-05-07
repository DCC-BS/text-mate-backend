from typing import Any

from llama_index.core.llms import (
    CompletionResponse,
    CompletionResponseGen,
    CustomLLM,
    LLMMetadata,
)
from llama_index.core.llms.callbacks import llm_completion_callback
from openai import OpenAI
from pydantic import Field

from text_mate_backend.utils.configuration import Configuration, get_config


class VllmCustom(CustomLLM):
    client: OpenAI = Field(default=OpenAI(), description="OpenAI client instance")
    config: Configuration | None = Field(default=None, description="Configuration instance")
    last_log: str = Field(default="", description="Last log message")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.config = get_config()
        self.client = OpenAI(
            api_key=self.config.openai_api_key,
            base_url=self.config.openai_api_base_url,
        )

        print(f"VLLM client initialized {self.config.openai_api_base_url}")

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(model_name=self.config.llm_model)

    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        completion = self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        output: str = completion.choices[0].message.content  # type: ignore

        self.last_log = completion.choices[0].model_dump_json()

        return CompletionResponse(text=output, raw=completion)

    @llm_completion_callback()
    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        response = ""

        stream = self.client.completions.create(
            model=self.config.llm_model,
            prompt=prompt,
            max_tokens=100,
            temperature=0.1,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:  # type: ignore
                content = chunk.choices[0].delta.content.replace("ß", "ss")  # type: ignore
                response += content
                yield CompletionResponse(text=response, delta=content)
