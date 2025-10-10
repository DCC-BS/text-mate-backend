from enum import Enum
from typing import Annotated

from pydantic import BaseModel


class Actions(str, Enum):
    PlainLanguage = "plain_language"
    EasyLanguage = "easy_language"
    BulletPoints = "bullet_points"
    Summarize = "summarize"
    SocialMediafy = "social_mediafy"
    Rewrite = "rewrite"
    Translate = "translate"


class QuickActionRequest(BaseModel):
    action: Annotated["Actions", "The quick action to perform"]
    text: Annotated[str, "The text to apply the action to"]
    options: Annotated[
        str,
        "Options to guide the rewriting process, such as writing style, target audience, and intent",
    ] = ""


class QuickActionContext(BaseModel):
    text: str
    options: str
