from typing import final

from pydantic import BaseModel, Field


class RewriteInput(BaseModel):
    text: str = Field(description="The original text to be rewritten")
    context: str = Field(description="Additional context to guide the text rewriting")
    writing_style: str = Field(default="general", description="The desired writing style for the rewritten text")
    target_audience: str = Field(default="general", description="The target audience for the rewritten text")
    intend: str = Field(default="general", description="The purpose or intention of the text")


@final
class TextRewriteOptions(BaseModel):
    writing_style: str = Field(default="general", description="The writing style to use for the rewritten text")
    target_audience: str = Field(default="general", description="The target audience for the rewritten text")
    intend: str = Field(default="general", description="The intention or purpose of the text")


@final
class RewriteResult(BaseModel):
    rewritten_text: str = Field(description="The rewritten text alternative")
