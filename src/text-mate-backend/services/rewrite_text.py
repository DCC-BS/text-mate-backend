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
    writing_style: str = dspy.InputField(
        desc="""The writing style to use for the rewritten text.
                - general: General text
                - simple: Simple text
                - professional: Professional text
                - casual: Casual text
                - academic: Academic text
                - technical: Technical text""",
    )
    target_audience: str = dspy.InputField(
        desc="""The target audience to use for the rewritten text.
                - general: General audience
                - young: Young audience
                - adult: Adult audience
                - children: Children audience""",
    )
    intend: str = dspy.InputField(
        desc="""The intend to use for the rewritten text.
                - general: General text
                - persuasive: Persuasive text
                - informative: Informative text
                - descriptive: Descriptive text
                - narrative: Narrative text
                - entertaining: Entertaining text""",
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

        response = module(
            text=text,
            context=context,
            writing_style=options.writing_style,
            target_audience=options.target_audience,
            intend=options.intend,
        )

        out_options: List[str] = response.options
        out_options = list(map(lambda option: option.replace("<rewrite>", text).replace("ß", "ss"), out_options))

        return right(RewriteResult(options=out_options))
