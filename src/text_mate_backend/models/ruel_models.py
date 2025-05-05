from pydantic import BaseModel, Field


class Ruel(BaseModel):
    name: str = Field(description="A descriptive name for the rule")
    description: str = Field(description="Description of the rule")
    file_name: str = Field(description="Filename of the source document")
    page_number: int = Field(description="Page number of the source document")
    example: str = Field(description="Example of the rule in use")


class RuelValidation(Ruel):
    """
    Validation class for Ruel.
    This class is used to validate the Ruel model.
    """

    reason: str = Field(description="Description of the rule violation")
    source: str = Field(description="Section in the text where the rule is violated")


class RuelsContainer(BaseModel):
    rules: list[Ruel] = Field(description="All violations of the rules")

    @property
    def document_names(self) -> set[str]:
        """
        Get the unique document names from the rules.
        """
        return {rule.file_name for rule in self.rules}


class RuelsValidationContainer(BaseModel):
    rules: list[RuelValidation] = Field(description="All violations of the rules")
