from typing import final

from pydantic import BaseModel, Field


@final
class TextRewriteOptions(BaseModel):
    writing_style: str = Field(default="general", description="The writing style to use for the rewritten text")
    target_audience: str = Field(default="general", description="The target audience for the rewritten text")
    intend: str = Field(default="general", description="The intention or purpose of the text")


@final
class RewriteResult(BaseModel):
    options: list[str] = Field(description="List of rewritten text alternatives")
