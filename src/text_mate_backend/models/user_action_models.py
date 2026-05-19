from pydantic.main import BaseModel


class UserActionMeta(BaseModel):
    id: str
    name: str


class UserAction(UserActionMeta):
    content: str
    groups: list[str] = []


class UserActionGetResponse(BaseModel):
    actions: list[UserActionMeta]
