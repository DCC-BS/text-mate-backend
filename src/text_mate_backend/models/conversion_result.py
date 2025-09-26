from pydantic import BaseModel


class ConversionResult(BaseModel):
    html: str


class ConversionOutput(BaseModel):
    html: str
