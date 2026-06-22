from pydantic import BaseModel, Field


class Rule(BaseModel):
    name: str = Field(description="A descriptive name for the rule in the original language")
    description: str = Field(description="Description of the rule in the original language")
    file_name: str = Field(description="Filename of the source PDF document")
    page_number: int = Field(description="Page number of the source document")
    example: str = Field(description="Example of the rule in use")
    collection: str = Field(
        description="Logical collection key used for filtering (matches RuleDocumentDescription.id)"
    )


class RulesContainer(BaseModel):
    rules: list[Rule] = Field(description="All rules to check")

    @property
    def document_names(self) -> set[str]:
        return {rule.collection for rule in self.rules}


class Violation(BaseModel):
    """Lean LLM output model — only what the LLM needs to return.
    Position resolution happens on the backend."""

    rule_name: str = Field(description="Name der Regel, die verletzt wurde (exakt wie in der Regeldokumentation)")
    reason: str = Field(description="Kurze Beschreibung des Verstosses in der Sprache des Textes")
    proposal: str = Field(description="Konkreter Verbesserungsvorschlag in der Sprache des Textes")
    source: str = Field(description="Exakter Textausschnitt aus dem Eingabetext, der gegen die Regel verstosst")


class RulesValidationResult(BaseModel):
    """LLM output type."""

    violations: list[Violation] = Field(description="All violations found in the text")


class ViolationResult(BaseModel):
    """API response model — violation with resolved character positions."""

    rule_name: str = Field(description="Name of the violated rule")
    reason: str = Field(description="Description of the rule violation")
    proposal: str = Field(description="Proposed solution to the rule violation")
    source: str = Field(description="Exact text snippet from the input that violates the rule")
    file_name: str = Field(description="Filename of the source PDF document for this rule")
    page_number: int = Field(description="Page number in the source document for this rule")
    start: int = Field(description="Start character position (0-based) of the violating text")
    end: int = Field(description="End character position (exclusive) of the violating text")


class RulesValidationContainer(BaseModel):
    """Streaming response type — violations plus progress counters."""

    violations: list[ViolationResult] = Field(description="Violations found in this batch")
    checked: int = Field(default=0, description="Number of rules checked so far")
    total: int = Field(default=0, description="Total number of rules to check")


class RuleDocumentDescription(BaseModel):
    title: str = Field(description="Title of the document")
    description: str = Field(description="Description of the document")
    author: str = Field(description="Author of the document")
    edition: str = Field(description="Edition of the document")
    id: str = Field(description="Collection identifier matching Rule.collection")
    files: list[str] = Field(description="Downloadable PDF filenames for this collection")
    access: list[str] = Field(description="Access permissions for the document, e.g., 'all' for public access")
