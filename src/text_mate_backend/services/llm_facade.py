from typing import Any, Generator, Type, TypeVar, cast

from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.prompts import PromptTemplate
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMFacade:
    def __init__(self, llm: LLM):
        self.llm = llm

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """
        Complete a prompt using the LLM.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters to pass to the completion API

        Returns:
            The completed text from the LLM
        """
        response = self.llm.complete(prompt, **kwargs)
        return response.text

    def stream_complete(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """
        Stream a completion using the LLM.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters to pass to the completion API

        Returns:
            The streamed text from the LLM
        """

        for completion in self.llm.stream_complete(prompt, **kwargs):
            if completion.delta is not None:
                yield completion.delta

    def stream_chat(self, messages: list[ChatMessage], **kwargs: Any) -> Generator[str, None, None]:
        """
        Complete a chat conversation using the LLM.

        Args:
            messages: The list of chat messages
            **kwargs: Additional parameters to pass to the chat API

        Returns:
            The completed chat response from the LLM
        """
        for response in self.llm.stream_chat(messages, **kwargs):
            if response.delta is not None:
                yield response.delta

    def structured_predict[T](
        self,
        response_type: Type[T],
        prompt: PromptTemplate,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> T:
        """
        Predict a structured response using the LLM.

        Args:
            prompt: The structured prompt template
            **kwargs: Additional parameters to pass to the prediction API

        Returns:
            The predicted structured response from the LLM with the specified type T
        """

        sllm = self.llm.as_structured_llm(cast(Type[BaseModel], response_type))
        response: T = sllm.structured_predict(response_type, prompt, llm_kwargs=llm_kwargs, **prompt_args)
        return response
