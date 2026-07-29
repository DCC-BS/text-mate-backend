from pydantic.fields import Field
from pydantic.main import BaseModel


class UserActionMeta(BaseModel):
    id: str
    name: str
    tooltip: str | None


class UserAction(UserActionMeta):
    content: str
    groups: list[str] = []
    tooltip: str | None


class UserActionGetResponse(BaseModel):
    actions: list[UserActionMeta]
