from typing import Annotated

from pydantic import BaseModel

from text_mate_backend.services.actions.quick_action_service import Actions


class QuickActionRequest(BaseModel):
    action: Annotated[Actions, "The quick action to perform"]
    text: Annotated[str, "The text to apply the action to"]
