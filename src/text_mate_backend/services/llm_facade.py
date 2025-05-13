from typing import Generator, Type, TypeVar

from llama_index.core.llms import LLM
from llama_index.core.prompts import PromptTemplate

T = TypeVar("T")


class LLMFacade:
    def __init__(self, llm: LLM):
        self.llm = llm

    def complete(self, prompt: str, **kwargs) -> str:
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

    def stream_complete(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        Stream a completion using the LLM.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters to pass to the completion API

        Returns:
            The streamed text from the LLM
        """

        for completion in self.llm.stream_complete(prompt, **kwargs):
            yield completion.delta

    def structured_predict[T](
        self,
        response_type: Type[T],
        prompt: PromptTemplate,
        llm_kwargs: dict[str, any] | None = None,
        **prompt_args: any,
    ) -> T:
        """
        Predict a structured response using the LLM.

        Args:
            prompt: The structured prompt template
            **kwargs: Additional parameters to pass to the prediction API

        Returns:
            The predicted structured response from the LLM with the specified type T
        """

        sllm = self.llm.as_structured_llm(response_type)
        response = sllm.structured_predict(response_type, prompt, llm_kwargs=llm_kwargs, **prompt_args)
        return response
