from typing import List, final

import dspy  # type: ignore
from functional_monads.either import Either, right

from models.text_rewrite_models import RewriteResult, TextRewriteOptions
from utils.configuration import config


class RewirteInfo(dspy.Signature):
    """
    Give alternatives to the text in respect of the domain and the formality.
    """

    text: str = dspy.InputField(desc="The text to be rewritten")
    context: str = dspy.InputField(desc="The full text of the document, text to be rewritten is marked with <rewrite>")
    formality: str = dspy.InputField(desc="The formality to use for the rewritten text")
    domain: str = dspy.InputField(
        desc="""The domain to use for the rewritten text.
                - general: General text
                - report: Text for a report or document
                - email: Text for an email
                - socialMedia: Text for social media post (e.g., Twitter, Facebook, etc.)
                - technical: Technical text""",
    )
    options: List[str] = dspy.OutputField(desc="A list of alternative texts")


@final
class TextRewriteService:
    def __init__(self) -> None:
        lm = dspy.LM(
            model="hosted_vllm/Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4",
            api_base=config.openai_api_base_url,
            api_key=config.openai_api_key,
            max_tokens=1000,
            temperature=0.6,
        )
        dspy.configure(lm=lm)

    def rewrite_text(self, text: str, context: str, options: TextRewriteOptions) -> Either[str, RewriteResult]:
        """Corrects the input text based on given options.
        Returns Either[str, str] where:
        - Left(str) contains error message
        - Right(str) contains corrected text
        """

        module = dspy.Predict(RewirteInfo)
        response = module(text=text, context=context, domain=options.domain, formality=options.formality)

        out_options: List[str] = response.options
        out_options = list(map(lambda option: option.replace("<rewrite>", text).replace("ß", "ss"), out_options))

        return right(RewriteResult(options=out_options))
