from typing import Any, Dict, List, Optional, Union, final

from llama_index.core.llms import CompletionResponse, CompletionResponseGen, CustomLLM, LLMMetadata
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.llms.function_calling import FunctionCallingLLM
from openai import OpenAI
from openai.types.chat import ChatCompletionToolParam
from pydantic import Field

from text_mate_backend.utils.configuration import Configuration


@final
class QwenVllm(CustomLLM):
    client: OpenAI = Field(default=OpenAI(api_key=""), description="OpenAI client instance")
    config: Configuration | None = Field(default=None, description="Configuration instance")
    last_log: str = Field(default="", description="Last log message")

    def __init__(self, config: Configuration, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.config = config
        self.client = OpenAI(
            api_key=self.config.openai_api_key,
            base_url=self.config.openai_api_base_url,
        )

        print(f"""VLLM client initialized:
              url: {self.config.openai_api_base_url}
              key: {self.config.openai_api_key}""")

    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(model_name=self.config.llm_model, is_chat_model=True, is_function_calling_model=False)

    @llm_completion_callback()
    def complete(
        self,
        prompt: str,
        tools: Optional[List[ChatCompletionToolParam]] = None,
        tool_choice: Optional[Union[str, Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        """
        Complete a prompt with optional tool usage.

        Args:
            prompt: The input prompt
            tools: List of tools available to the model
            tool_choice: Controls how the model uses tools. Can be "none", "auto", or a specific tool name
            **kwargs: Additional parameters to pass to the completion API

        Returns:
            CompletionResponse with text and raw API response
        """
        completion_kwargs = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt + " /no_think"}],
            "presence_penalty": 1.5,
            "top_p": 0.8,
            "temperature": 0.7,
            "extra_body": {"top_k": 20},
        }

        # Add tools if provided
        if tools:
            completion_kwargs["tools"] = tools

        # Add tool_choice if provided
        if tool_choice:
            completion_kwargs["tool_choice"] = tool_choice

        completion = self.client.chat.completions.create(**completion_kwargs)

        message = completion.choices[0].message
        output: str = message.content or ""  # Handle None case explicitly
        tool_calls = message.tool_calls  # New: Capture tool calls

        self.last_log = completion.choices[0].model_dump_json()

        return CompletionResponse(text=output, raw=completion, additional_kwargs={"tool_calls": tool_calls})

    @llm_completion_callback()
    def stream_complete(
        self,
        prompt: str,
        tools: Optional[List[ChatCompletionToolParam]] = None,
        tool_choice: Optional[Union[str, Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> CompletionResponseGen:
        """
        Stream complete a prompt with optional tool usage.

        Args:
            prompt: The input prompt
            tools: List of tools available to the model
            tool_choice: Controls how the model uses tools
            **kwargs: Additional parameters to pass to the completion API

        Yields:
            CompletionResponse chunks with progressive text and deltas
        """
        response = ""

        # Use chat.completions instead of completions for consistency with non-streaming behavior
        completion_kwargs = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt + " /no_think"}],
            "presence_penalty": 1.5,
            "top_p": 0.8,
            "temperature": 0.7,
            "extra_body": {"top_k": 20},
            "stream": True,
        }

        # Add tools if provided
        if tools:
            completion_kwargs["tools"] = tools

        # Add tool_choice if provided
        if tool_choice:
            completion_kwargs["tool_choice"] = tool_choice

        stream = self.client.chat.completions.create(**completion_kwargs)

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content.replace("ß", "ss")
                response += content
                yield CompletionResponse(text=response, delta=content)

            # Handle tool calls in streaming mode
            if chunk.choices and hasattr(chunk.choices[0].delta, "tool_calls") and chunk.choices[0].delta.tool_calls:
                # For tool calls in streaming, we just log them but actual tool execution
                # should be handled by the caller after the stream is complete
                self.last_log = f"Tool call received in chunk: {chunk.model_dump_json()}"
