from pydantic import BaseModel, Field, field_validator


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


class DetectionViolation(BaseModel):
    """Step 1 LLM output model — detection only.
    Proposal generation happens in a separate call; position resolution happens on the backend."""

    rule_name: str = Field(description="Name der Regel, die verletzt wurde (exakt wie in der Regeldokumentation)")
    reason: str = Field(description="Kurze Beschreibung des Verstosses in der Sprache des Textes")
    source: str = Field(description="Exakter Textausschnitt aus dem Eingabetext, der gegen die Regel verstosst")


class DetectionResult(BaseModel):
    """Step 1 LLM output type — list of detected violations."""

    violations: list[DetectionViolation] = Field(description="All violations found in the text")


class ProposalRequest(BaseModel):
    """Step 2 deps type — context for generating a single proposal."""

    rule: Rule = Field(description="The rule that was violated")
    source: str = Field(description="Exakter Textausschnitt aus dem Eingabetext, der gegen die Regel verstosst")
    reason: str = Field(description="Kurze Beschreibung des Verstosses in der Sprache des Textes")
    context_sentence: str = Field(description="Der Satz, der den Verstoss enthält, als Kontext für den Vorschlag")


class ViolationRange(BaseModel):
    """Half-open character range into the source text.

    The indexing scheme depends on the consumer: internally (e.g.
    ``ResolvedDetection.range``) the offsets are Python code points; at the API
    boundary (``ViolationResult.range``) they are UTF-16 code units. See
    ``utils.text_offsets.to_utf16_offset`` for the translation between the two.
    """

    start: int = Field(description="Start position (0-based, inclusive) of the violating text")
    end: int = Field(description="End position (exclusive) of the violating text")


class ResolvedDetection(BaseModel):
    """Intermediate result after step 1 (detection) and position resolution.
    Holds everything needed to request a proposal in step 2 and to build a
    ViolationResult once the proposal is returned."""

    rule_name: str
    reason: str
    source: str
    range: ViolationRange
    file_name: str
    page_number: int
    collection: str


class ViolationResult(BaseModel):
    """API response model — violation with resolved character positions."""

    rule_name: str = Field(description="Name of the violated rule")
    reason: str = Field(description="Description of the rule violation")
    proposal: str = Field(description="Proposed solution to the rule violation")
    source: str = Field(description="Exact text snippet from the input that violates the rule")
    file_name: str = Field(description="Filename of the source PDF document for this rule")
    page_number: int = Field(description="Page number in the source document for this rule")
    range: ViolationRange = Field(
        description="Character range of the violating text, as UTF-16 code-unit indices (JavaScript-compatible)"
    )
    collection: str = Field(
        description="Logical collection key used for filtering (matches RuleDocumentDescription.id)"
    )


class RulesValidationContainer(BaseModel):
    """Streaming response type — violations plus progress counters."""

    violations: list[ViolationResult] = Field(description="Violations found in this batch")
    checked: int = Field(default=0, description="Number of rules checked so far")
    total: int = Field(default=0, description="Total number of rules to check")


class DocumentFileInfo(BaseModel):
    name: str = Field(description="PDF filename, downloadable via GET /advisor/doc/{name}")
    title: str = Field(default="", description="Human-readable display name of the document")
    description: str = Field(default="", description="Short description of the document content")
    size: int = Field(default=0, description="File size in bytes; 0 if the file is not bundled")


class RuleDocumentDescription(BaseModel):
    title: str = Field(description="Title of the document")
    description: str = Field(description="Description of the document")
    author: str = Field(description="Author of the document")
    edition: str = Field(description="Edition of the document")
    id: str = Field(description="Collection identifier matching Rule.collection")
    files: list[DocumentFileInfo] = Field(description="Downloadable PDF files for this collection")
    rule_count: int = Field(default=0, description="Number of bundled rules in this collection")
    access: list[str] = Field(description="Access permissions for the document, e.g., 'all' for public access")

    @field_validator("files", mode="before")
    @classmethod
    def _coerce_file_names(cls, value: object) -> object:
        """Accept bare filename strings (meta JSON format) as name-only entries."""
        if isinstance(value, list):
            return [DocumentFileInfo(name=f, size=0) if isinstance(f, str) else f for f in value]
        return value
