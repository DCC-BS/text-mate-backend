from enum import Enum

from openai import OpenAI
from utils.configuration import config

from services.actions.bullet_points_action import bullet_points
from services.actions.shorten_action import shorten
from services.actions.simplify_action import simplify
from services.actions.social_media_action import social_mediafy
from services.actions.summarize_action import summarize


class Actions(str, Enum):
    Simplify = "simplify"
    Shorten = "shorten"
    BulletPoints = "bullet_points"
    Summarize = "summarize"
    SocialMediafy = "social_mediafy"


class QuickActionService:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_api_base_url,
        )

    def run(self, action: Actions, text: str):
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
            case _:
                raise ValueError(f"Unknown action: {action}")
