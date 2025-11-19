from pydantic import BaseModel


class ConversionResult(BaseModel):
    html: str
