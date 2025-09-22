from pydantic import BaseModel


class ConversionResult:
    markdown: str

    def __init__(self, markdown: str):
        self.markdown = markdown


class ConversionOutput(BaseModel):
    markdown: str
