from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture
from returns.result import Failure, Success

from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.text_rewrite_models import RewriteResult
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.services.rewrite_text import RewriteOutput, TextRewriteService


@pytest.fixture
def mock_llm_facade(mocker: MockerFixture) -> Mock:
    """
    Provides a mock LLMFacade for testing.

    Args:
        mocker: The pytest-mock fixture

    Returns:
        A mock DspyFacade object
    """
    mock_facade: LLMFacade = mocker.Mock(spec=LLMFacade)
    return mock_facade


class TestTextRewriteService:
    """Tests for the TextRewriteService class."""

    def test_init(self, mock_llm_facade: Mock) -> None:
        """
        Test that TextRewriteService is initialized correctly.

        Args:
            mock_llm_facade: The mock LLMFacade instance
        """
        # Act
        service = TextRewriteService(llm_facade=mock_llm_facade)

        # Assert
        assert isinstance(service, TextRewriteService)

    def test_rewrite_text_success(self, mock_llm_facade: Mock) -> None:
        """
        Test that rewrite_text returns RewriteResult with processed options on success.

        Args:
            mock_llm_facade: The mock LLMFacade instance
        """
        # Arrange
        input_text = "Hello world"
        context = "This is a <rewrite>Hello world</rewrite> context"
        options = "writing_style: professional\n target_audience: adult\n intend: informative"

        # Mock the structured_predict method to return a RewriteOutput with rewritten_text
        mock_response = Mock(spec=RewriteOutput)
        mock_response.rewritten_text = "Option 1"
        mock_llm_facade.structured_predict.return_value = mock_response

        service = TextRewriteService(llm_facade=mock_llm_facade)

        # Act
        result = service.rewrite_text(input_text, context, options)

        # Assert
        assert isinstance(result, Success)
        rewrite_result = result.unwrap()
        assert isinstance(rewrite_result, RewriteResult)
        assert rewrite_result.rewritten_text == "Option 1"

        # Verify that LLMFacade.structured_predict was called correctly
        mock_llm_facade.structured_predict.assert_called_once()

    def test_rewrite_text_with_special_characters(self, mock_llm_facade: Mock) -> None:
        """
        Test that rewrite_text handles special characters like 'ß' correctly.

        Args:
            mock_llm_facade: The mock LLMFacade instance
        """
        # Arrange
        input_text = "Straße"
        context = "This is a <rewrite>Straße</rewrite> context"
        options = ""

        # Mock the structured_predict method to return a response with special characters
        mock_response = Mock(spec=RewriteOutput)
        mock_response.rewritten_text = "Die große Straße"
        mock_llm_facade.structured_predict.return_value = mock_response

        service = TextRewriteService(llm_facade=mock_llm_facade)

        # Act
        result = service.rewrite_text(input_text, context, options)

        # Assert
        assert isinstance(result, Success)
        rewrite_result = result.unwrap()
        assert "ß" not in rewrite_result.rewritten_text
        assert "ss" in rewrite_result.rewritten_text
        assert rewrite_result.rewritten_text == "Die grosse Strasse"

    def test_rewrite_text_with_rewrite_tag_replacement(self, mock_llm_facade: Mock) -> None:
        """
        Test that rewrite_text correctly replaces <rewrite> tags with the original text.

        Args:
            mock_llm_facade: The mock LLMFacade instance
        """
        # Arrange
        input_text = "Hello world"
        context = "This is a <rewrite>Hello world</rewrite> context"
        options = ""

        # Mock the structured_predict method to return text with <rewrite> tags
        mock_response = Mock(spec=RewriteOutput)
        mock_response.rewritten_text = "<rewrite> is replaced"
        mock_llm_facade.structured_predict.return_value = mock_response

        service = TextRewriteService(llm_facade=mock_llm_facade)

        # Act
        result = service.rewrite_text(input_text, context, options)

        # Assert
        assert isinstance(result, Success)
        rewrite_result = result.unwrap()
        assert rewrite_result.rewritten_text == "Hello world is replaced"

    def test_rewrite_text_exception_handling(self, mock_llm_facade: Mock) -> None:
        """
        Test that rewrite_text properly handles exceptions using the @safe decorator.

        Args:
            mock_llm_facade: The mock LLMFacade instance
        """
        # Arrange
        input_text = "Hello world"
        context = "This is a context"
        options = ""

        # Mock the structured_predict method to raise an exception
        mock_llm_facade.structured_predict.side_effect = Exception("API error")

        service = TextRewriteService(llm_facade=mock_llm_facade)

        # Act
        result = service.rewrite_text(input_text, context, options)

        # Assert
        assert isinstance(result, Failure)
        assert isinstance(result.failure(), ApiErrorException)
        assert str(result.failure().error_response["debugMessage"]) == "API error"
