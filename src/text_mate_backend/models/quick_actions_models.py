from enum import Enum
from typing import Annotated, TypeVar

from pydantic import BaseModel

from text_mate_backend.models.output_models import TypedDict

TExtra = TypeVar("TExtra", bound=dict)


class Actions(str, Enum):
    PlainLanguage = "plain_language"
    BulletPoints = "bullet_points"
    Summarize = "summarize"
    SocialMediafy = "social_mediafy"
    Formaility = "formality"
    Medium = "medium"
    Custom = "custom"
    Proofread = "proofread"


class QuickActionRequest(BaseModel):
    action: Annotated["Actions", "The quick action to perform"]
    text: Annotated[str, "The text to apply the action to"]
    options: Annotated[
        str,
        "Options to guide the rewriting process, such as writing style, target audience, and intent",
    ] = ""


class CurrentUser(TypedDict):
    family_name: str
    given_name: str
    email: str


class QuickActionContext[TExtra](BaseModel):
    text: str
    options: str
    language: str | None = None
    extras: TExtra | None = None
