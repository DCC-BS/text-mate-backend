from typing import List

from pydantic import BaseModel


class TextRewriteOptions(BaseModel):
    writing_style: str = "general"
    target_audience: str = "general"
    intend: str = "general"


class RewriteResult(BaseModel):
    options: List[str]
