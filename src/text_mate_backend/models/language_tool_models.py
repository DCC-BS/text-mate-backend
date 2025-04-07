from typing import final

from pydantic import BaseModel, Field


@final
class LanguageToolSoftware(BaseModel):
    name: str = Field(description="Name of the LanguageTool software")
    version: str = Field(description="Version of the LanguageTool software")
    buildDate: str = Field(description="Build date of the LanguageTool software")


@final
class LanguageToolDetectedLanguage(BaseModel):
    name: str = Field(description="Name of the detected language")
    code: str = Field(description="Language code of the detected language")


@final
class LanguageToolLanguage(BaseModel):
    name: str = Field(description="Name of the language")
    code: str = Field(description="Language code")
    detectedLanguage: LanguageToolDetectedLanguage = Field(description="Information about the detected language")


@final
class LanguageToolReplacement(BaseModel):
    value: str = Field(description="Suggested replacement text for the error")


@final
class LanguageToolContext(BaseModel):
    text: str = Field(description="Text context surrounding the error")
    offset: int = Field(description="Offset position of the error within the context")
    length: int = Field(description="Length of the error text")


@final
class LanguageToolMatch(BaseModel):
    message: str = Field(description="Full error message describing the issue")
    shortMessage: str = Field(description="Short version of the error message")
    offset: int = Field(description="Offset position of the error in the original text")
    length: int = Field(description="Length of the error text")
    replacements: list[LanguageToolReplacement] = Field(description="Suggested replacements for the error")
    context: LanguageToolContext = Field(description="Context information about the error")


@final
class LanguageToolResponse(BaseModel):
    software: LanguageToolSoftware = Field(description="Information about the LanguageTool software")
    language: LanguageToolLanguage = Field(description="Information about the language used")
    matches: list[LanguageToolMatch] = Field(description="List of detected errors and their corrections")
