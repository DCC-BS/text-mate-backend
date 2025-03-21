from pydantic import BaseModel


class LanguageToolSoftware(BaseModel):
    name: str
    version: str
    buildDate: str


class LanguageToolDetectedLanguage(BaseModel):
    name: str
    code: str


class LanguageToolLanguage(BaseModel):
    name: str

    code: str
    detectedLanguage: LanguageToolDetectedLanguage


class LanguageToolReplacement(BaseModel):
    value: str


class LanguageToolContext(BaseModel):
    text: str
    offset: int
    length: int


class LanguageToolMatch(BaseModel):
    message: str
    shortMessage: str
    offset: int
    length: int
    replacements: list[LanguageToolReplacement]

    context: LanguageToolContext


class LanguageToolResponse(BaseModel):
    software: LanguageToolSoftware
    language: LanguageToolLanguage
    matches: list[LanguageToolMatch]
