from enum import StrEnum
from backend_common.fastapi_error_handling import ApiErrorCodes


class TextMateApiErrorCodes(StrEnum):
    NO_DOCUMENT = "no_document"
    CHECK_TEXT_ERROR = "check_text_error"
    LANGUAGE_TOOL_ERROR = "language_tool_error"
    REWRITE_TEXT_ERROR = "rewrite_text_error"
    INVALID_MIME_TYPE = "invalid_mime_type"
