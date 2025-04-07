from typing import Any, TypeVar, Type, Dict

import dspy  # type: ignore
from pydantic import BaseModel

from text_mate_backend.utils.configuration import Configuration

TSignature = TypeVar("TSignature", bound=Type[dspy.Signature])


class DspyInitOptions(BaseModel):
    """
    Options for initializing the Dspy service.
    """

    max_tokens: int = 1000
    temperature: float = 0.6


class DspyFacade:
    """
    Facade for the Dspy service.
    """

    def __init__(
        self,
        config: Configuration,
        options: DspyInitOptions,
    ):
        self.lm = dspy.LM(
            model=f"hosted_vllm/{config.llm_model}",
            api_base=config.openai_api_base_url,
            api_key=config.openai_api_key,
            max_tokens=options.max_tokens,
            temperature=options.temperature,
        )
        dspy.configure(lm=self.lm)

    def predict(self, signature: TSignature, **kwargs: Any) -> Any:
        """
        Predicts outputs using a DSPy signature with the provided input parameters.

        Args:
            signature: A DSPy Signature class (not instance)
            kwargs: Input parameters for the signature

        Returns:
            The prediction result from DSPy
        """

        module = dspy.Predict(signature)

        return module(**kwargs)
