from pydantic import BaseModel, Field


class Rule(BaseModel):
    name: str = Field(description="A descriptive name for the rule in the original language")
    description: str = Field(description="Description of the rule in the original language")
    file_name: str = Field(description="Filename of the source document")
    page_number: int = Field(description="Page number of the source document")
    example: str = Field(description="Example of the rule in use")


class RuelValidation(Rule):
    """
    Validation class for Ruel.
    This class is used to validate the Ruel model.
    """

    reason: str = Field(description="Description of the rule violation in the original language")
    proposal: str = Field(description="Proposed solution to the rule violation in the original language")
    source: str = Field(description="Section in the text where the rule is violated")


class RulesContainer(BaseModel):
    rules: list[Rule] = Field(description="All violations of the rules")

    @property
    def document_names(self) -> set[str]:
        """
        Get the unique document names from the rules.
        """
        return {rule.file_name for rule in self.rules}


class RulesValidationContainer(BaseModel):
    rules: list[RuelValidation] = Field(description="All violations of the rules")


class RuelDocumentDescription(BaseModel):
    title: str = Field(description="Title of the document")
    description: str = Field(description="Description of the document")
    author: str = Field(description="Author of the document")
    edition: str = Field(description="Edition of the document")
    file: str = Field(description="Filename of the document")
    access: list[str] = Field(description="Access permissions for the document, e.g., 'all' for public access")
