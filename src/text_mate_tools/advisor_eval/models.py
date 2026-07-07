from pydantic import BaseModel, Field


class ExpectedViolation(BaseModel):
    """A single labeled ground-truth violation inside an eval case text."""

    rule_name: str = Field(description="Exact rule name as it appears in assets/docs/rules")
    source: str = Field(description="Exact substring of the case text that violates the rule")
    occurrence: int = Field(
        default=1,
        ge=1,
        description="1-based index selecting which occurrence of `source` in the text is meant",
    )
    alt_rule_names: list[str] = Field(
        default_factory=list,
        description="Sibling rule names that are also acceptable attributions for this violation",
    )


class EvalCase(BaseModel):
    """A text with exhaustively labeled rule violations."""

    id: str = Field(description="Unique case identifier")
    description: str = Field(default="", description="What this case is probing")
    collections: list[str] = Field(description="Rule collections to check the text against")
    text: str = Field(description="The input text")
    expected: list[ExpectedViolation] = Field(
        default_factory=list,
        description="All violations present in the text; empty for clean negative cases",
    )


class PredictedViolation(BaseModel):
    """A violation reported by the advisor, reduced to what scoring needs."""

    rule_name: str
    start: int = Field(description="Start character position (0-based)")
    end: int = Field(description="End character position (exclusive)")
    source: str = ""
