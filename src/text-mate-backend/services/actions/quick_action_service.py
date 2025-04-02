from enum import Enum, auto

from fastapi.responses import StreamingResponse
from openai import OpenAI
from utils.configuration import config

from services.actions.simplify_action import simplify


class Actions(str, Enum):
    Simplify = "simplify"


class QuickActionService:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_api_base_url,
        )

    def run(self, action: Actions, text: str) -> StreamingResponse:
        match action:
            case Actions.Simplify:
                return simplify(text, self.client)
            case _:
                raise ValueError(f"Unknown action: {action}")
