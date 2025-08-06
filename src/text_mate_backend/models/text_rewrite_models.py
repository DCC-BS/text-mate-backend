from pydantic import BaseModel, Field


class RewriteInput(BaseModel):
    text: str = Field(description="The original text to be rewritten")
    context: str = Field(description="Additional context to guide the text rewriting")
    options: str = Field(
        description="Options to guide the rewriting process, such as writing style, target audience, and intend"
    )


class RewriteResult(BaseModel):
    rewritten_text: str = Field(description="The rewritten text alternative")
