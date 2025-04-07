import pytest
from pytest_mock import MockerFixture
from returns.pipeline import is_successful
from returns.result import Failure, ResultE, Success

from text_mate_backend.models.language_tool_models import (
    LanguageToolContext,
    LanguageToolDetectedLanguage,
    LanguageToolLanguage,
    LanguageToolMatch,
    LanguageToolReplacement,
    LanguageToolResponse,
    LanguageToolSoftware,
)
from text_mate_backend.models.text_corretion_models import CorrectionResult, TextCorrectionOptions
from text_mate_backend.services.language_tool_service import LanguageToolService
from text_mate_backend.services.text_correction_language_tool import TextCorrectionService
from text_mate_backend.utils.configuration import Configuration


@pytest.fixture
def mock_config(mocker: MockerFixture) -> Configuration:
    config = mocker.Mock(spec=Configuration)
    config.language_tool_api_url = "http://localhost:8010"
    return config  # type: ignore


@pytest.fixture
def mock_language_tool_service(mocker: MockerFixture) -> LanguageToolService:
    service = mocker.Mock(spec=LanguageToolService)
    # Instead of setting return_value on check_text, make check_text a callable that returns the desired Result
    service.check_text = mocker.Mock()
    return service  # type: ignore


@pytest.fixture
def text_correction_service(
    mock_config: Configuration, mock_language_tool_service: LanguageToolService
) -> TextCorrectionService:
    return TextCorrectionService(config=mock_config, language_tool_Service=mock_language_tool_service)


def create_sample_language_tool_response() -> LanguageToolResponse:
    """Helper function to create a sample LanguageToolResponse for testing"""
    return LanguageToolResponse(
        software=LanguageToolSoftware(name="LanguageTool", version="5.7", buildDate="2022-03-01 12:00"),
        language=LanguageToolLanguage(
            name="German", code="de", detectedLanguage=LanguageToolDetectedLanguage(name="German", code="de")
        ),
        matches=[
            LanguageToolMatch(
                message="This is a grammar error",
                shortMessage="Grammar error",
                offset=10,
                length=5,
                replacements=[LanguageToolReplacement(value="corrected text")],
                context=LanguageToolContext(text="This is a sample text with error in it", offset=10, length=5),
            ),
            LanguageToolMatch(
                message="This is a spelling error",
                shortMessage="Spelling error",
                offset=30,
                length=4,
                replacements=[LanguageToolReplacement(value="fixed"), LanguageToolReplacement(value="corrected")],
                context=LanguageToolContext(text="Another sample with erro in the text", offset=19, length=4),
            ),
        ],
    )


class TestTextCorrectionService:
    def test_correct_text_success(
        self, text_correction_service: TextCorrectionService, mock_language_tool_service: LanguageToolService
    ) -> None:
        """Test successful text correction"""
        # Arrange
        text: str = "This is a sample text with some errors."
        options: TextCorrectionOptions = TextCorrectionOptions()
        language_tool_response: LanguageToolResponse = create_sample_language_tool_response()

        # Setup mock to return Success with our prepared response - updated approach
        mock_language_tool_service.check_text.return_value = Success(language_tool_response)  # type: ignore

        # Act
        result: ResultE[CorrectionResult] = text_correction_service.correct_text(text, options)

        # Assert
        assert is_successful(result)
        correction_result: CorrectionResult = result.unwrap()
        assert isinstance(correction_result, CorrectionResult)
        assert correction_result.original == text
        assert len(correction_result.blocks) == 2

        # Get the expected data from our test helper
        lt_response: LanguageToolResponse = create_sample_language_tool_response()

        # Verify first correction block
        first_match: LanguageToolMatch = lt_response.matches[0]
        first_context: LanguageToolContext = first_match.context
        expected_original: str = first_context.text[first_context.offset : first_context.offset + first_context.length]

        assert correction_result.blocks[0].original == expected_original
        assert correction_result.blocks[0].corrected == [r.value for r in first_match.replacements]
        assert correction_result.blocks[0].explanation == first_match.message
        assert correction_result.blocks[0].offset == first_match.offset
        assert correction_result.blocks[0].length == first_match.length

        # Verify second correction block
        second_match: LanguageToolMatch = lt_response.matches[1]
        second_context: LanguageToolContext = second_match.context
        expected_original = second_context.text[second_context.offset : second_context.offset + second_context.length]

        assert correction_result.blocks[1].original == expected_original
        assert correction_result.blocks[1].corrected == [r.value for r in second_match.replacements]
        assert correction_result.blocks[1].explanation == second_match.message
        assert correction_result.blocks[1].offset == second_match.offset
        assert correction_result.blocks[1].length == second_match.length

    def test_correct_text_failure(
        self, text_correction_service: TextCorrectionService, mock_language_tool_service: LanguageToolService
    ) -> None:
        """Test handling of LanguageToolService failure"""
        # Arrange
        text: str = "This is a sample text."
        options: TextCorrectionOptions = TextCorrectionOptions()
        error_message: str = "API connection error"

        # Setup mock to return Failure with error message
        mock_language_tool_service.check_text.return_value = Failure(error_message)  # type: ignore

        # Act
        result: ResultE[CorrectionResult] = text_correction_service.correct_text(text, options)

        # Assert
        assert isinstance(result, Failure)
        assert result.failure() == error_message

    def test_correct_text_empty_matches(
        self, text_correction_service: TextCorrectionService, mock_language_tool_service: LanguageToolService
    ) -> None:
        """Test correction with no errors found"""
        # Arrange
        text: str = "This is a perfect text with no errors."
        options: TextCorrectionOptions = TextCorrectionOptions()

        # Create response with no matches
        empty_response: LanguageToolResponse = LanguageToolResponse(
            software=LanguageToolSoftware(name="LanguageTool", version="5.7", buildDate="2022-03-01 12:00"),
            language=LanguageToolLanguage(
                name="German", code="de", detectedLanguage=LanguageToolDetectedLanguage(name="German", code="de")
            ),
            matches=[],
        )

        # Setup mock to return Success with empty matches
        mock_language_tool_service.check_text.return_value = Success(empty_response)  # type: ignore

        # Act
        result: ResultE[CorrectionResult] = text_correction_service.correct_text(text, options)

        # Assert
        assert isinstance(result, Success)
        correction_result: CorrectionResult = result.unwrap()
        assert isinstance(correction_result, CorrectionResult)
        assert correction_result.original == text
        assert len(correction_result.blocks) == 0
