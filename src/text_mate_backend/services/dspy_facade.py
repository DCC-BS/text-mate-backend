import time
from typing import Any, Type, TypeVar

import dspy  # type: ignore
from pydantic import BaseModel

from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

TSignature = TypeVar("TSignature", bound=Type[dspy.Signature])
logger = get_logger("dspy_facade")


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
        logger.info("Initializing DspyFacade", max_tokens=options.max_tokens, temperature=options.temperature)

        model_name = f"hosted_vllm/{config.llm_model}"
        logger.info("Configuring LLM", model=model_name)

        self.lm = dspy.LM(
            model=model_name,
            api_base=config.openai_api_base_url,
            api_key=config.openai_api_key,
            max_tokens=options.max_tokens,
            temperature=options.temperature,
        )
        dspy.configure(lm=self.lm)
        logger.info("DspyFacade initialized successfully")

    def predict(self, signature: TSignature, **kwargs: Any) -> Any:
        """
        Predicts outputs using a DSPy signature with the provided input parameters.

        Args:
            signature: A DSPy Signature class (not instance)
            kwargs: Input parameters for the signature

        Returns:
            The prediction result from DSPy
        """
        signature_name = signature.__name__
        logger.info(f"Predicting with signature: {signature_name}", inputs=list(kwargs.keys()))

        # Log parameter lengths for debugging
        param_sizes = {k: len(str(v)) for k, v in kwargs.items()}
        logger.debug("Parameter sizes", param_sizes=param_sizes)

        start_time = time.time()
        try:
            module = dspy.Predict(signature)
            result = module(**kwargs)

            processing_time_ms = round((time.time() - start_time) * 1000)
            logger.info(
                f"DSPy prediction completed successfully",
                signature=signature_name,
                processing_time_ms=processing_time_ms,
            )

            return result

        except Exception as e:
            processing_time_ms = round((time.time() - start_time) * 1000)
            logger.error(
                f"DSPy prediction failed",
                signature=signature_name,
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=processing_time_ms,
            )
            raise
