from pydantic import BaseModel, Field


class UserActionMeta(BaseModel):
    id: str
    name: str
    tooltip: str | None = None


class UserAction(UserActionMeta):
    content: str
    groups: list[str] = Field(default_factory=list)
    tooltip: str | None = None


class UserActionGetResponse(BaseModel):
    actions: list[UserActionMeta]
