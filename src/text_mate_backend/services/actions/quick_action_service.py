from enum import Enum

from fastapi.responses import StreamingResponse
from openai import OpenAI
from returns.result import safe

from text_mate_backend.services.actions.bullet_points_action import bullet_points
from text_mate_backend.services.actions.shorten_action import shorten
from text_mate_backend.services.actions.simplify_action import simplify
from text_mate_backend.services.actions.social_media_action import social_mediafy
from text_mate_backend.services.actions.structure_action import structure_text
from text_mate_backend.services.actions.summarize_action import summarize
from text_mate_backend.utils.configuration import Configuration


class Actions(str, Enum):
    Simplify = "simplify"
    Shorten = "shorten"
    BulletPoints = "bullet_points"
    Summarize = "summarize"
    SocialMediafy = "social_mediafy"
    Structure = "structure"


class QuickActionService:
    def __init__(self, config: Configuration) -> None:
        self.client: OpenAI = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_api_base_url,
        )

    @safe
    def run(self, action: Actions, text: str) -> StreamingResponse:
        match action:
            case Actions.Simplify:
                return simplify(text, self.client)
            case Actions.Shorten:
                return shorten(text, self.client)
            case Actions.BulletPoints:
                return bullet_points(text, self.client)
            case Actions.Summarize:
                return summarize(text, self.client)
            case Actions.SocialMediafy:
                return social_mediafy(text, self.client)
            case Actions.Structure:
                return structure_text(text, self.client)
            case _:
                raise ValueError(f"Unknown action: {action}")
