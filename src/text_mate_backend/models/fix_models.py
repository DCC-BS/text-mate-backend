from pydantic import BaseModel, Field


class FixThread(BaseModel):
    source: str = Field(description="Exact text snippet from the input that should be fixed")
    proposal: str | None = Field(default=None, description="Proposed replacement for the source snippet")
    reason: str | None = Field(default=None, description="Short description of why the fix is needed")
    notes: list[str] = Field(
        default_factory=list, description="Additional notes to guide the rewrite, notes are written by the user."
    )


class FixRequest(BaseModel):
    text: str = Field(description="The original text to be corrected")
    threads: list[FixThread] = Field(default_factory=list, description="The fix threads to apply to the text")
