from typing import List, final

from pydantic import BaseModel


@final
class TextRewriteOptions:
    def __init__(self, domain: str = "general", formality: str = "formal"):
        self.domain = domain
        self.formality = formality


class RewriteResult(BaseModel):
    options: List[str]
