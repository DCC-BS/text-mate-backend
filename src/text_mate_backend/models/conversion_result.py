from pydantic import BaseModel


class ConversionResult:
    html: str

    def __init__(self, html: str):
        self.html = html


class ConversionOutput(BaseModel):
    html: str
