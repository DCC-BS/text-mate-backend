from typing import Any, List
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture
from returns.result import Failure, Success

from text_mate_backend.models.text_rewrite_models import RewriteResult, TextRewriteOptions
from text_mate_backend.services.dspy_facade import DspyFacade, DspyInitOptions
from text_mate_backend.services.rewrite_text import RewirteInfo, TextRewriteService


@pytest.fixture
def mock_dspy_facade(mocker: MockerFixture) -> Mock:
    """
    Provides a mock DspyFacade for testing.

    Args:
        mocker: The pytest-mock fixture

    Returns:
        A mock DspyFacade object
    """
    mock_facade = mocker.Mock(spec=DspyFacade)
    return mock_facade


@pytest.fixture
def mock_dspy_facade_factory(mock_dspy_facade: Mock) -> Mock:
    """
    Provides a mock factory function that returns a DspyFacade.

    Args:
        mock_dspy_facade: The mock DspyFacade fixture

    Returns:
        A mock factory function
    """
    return Mock(return_value=mock_dspy_facade)


class TestTextRewriteService:
    """Tests for the TextRewriteService class."""

    def test_init(self, mock_dspy_facade_factory: Mock) -> None:
        """
        Test that TextRewriteService is initialized correctly.

        Args:
            mock_dspy_facade_factory: Factory function that produces a mock DspyFacade
        """
        # Act
        service = TextRewriteService(dspy_facade_factory=mock_dspy_facade_factory)

        # Assert
        mock_dspy_facade_factory.assert_called_once()
        assert isinstance(service, TextRewriteService)
        options = mock_dspy_facade_factory.call_args[1]["options"]
        assert isinstance(options, DspyInitOptions)
        assert options.temperature == 0.6
        assert options.max_tokens == 1000

    def test_rewrite_text_success(self, mock_dspy_facade_factory: Mock, mock_dspy_facade: Mock) -> None:
        """
        Test that rewrite_text returns RewriteResult with processed options on success.

        Args:
            mock_dspy_facade_factory: Factory function that produces a mock DspyFacade
            mock_dspy_facade: The mock DspyFacade instance
        """
        # Arrange
        input_text = "Hello world"
        context = "This is a <rewrite>Hello world</rewrite> context"
        options = TextRewriteOptions(writing_style="professional", target_audience="adult", intend="informative")

        # Mock the predict method to return a RewirteInfo with rewritten_text
        mock_response = Mock(spec=RewirteInfo)
        mock_response.rewritten_text = "Option 1"
        mock_dspy_facade.predict.return_value = mock_response

        service = TextRewriteService(dspy_facade_factory=mock_dspy_facade_factory)

        # Act
        result = service.rewrite_text(input_text, context, options)

        # Assert
        assert isinstance(result, Success)
        rewrite_result = result.unwrap()
        assert isinstance(rewrite_result, RewriteResult)
        assert rewrite_result.rewritten_text == "Option 1"

        # Verify that DspyFacade.predict was called with correct parameters
        mock_dspy_facade.predict.assert_called_once_with(
            RewirteInfo,
            text=input_text,
            context=context,
            writing_style=options.writing_style,
            target_audience=options.target_audience,
            intend=options.intend,
        )

    def test_rewrite_text_with_special_characters(self, mock_dspy_facade_factory: Mock, mock_dspy_facade: Mock) -> None:
        """
        Test that rewrite_text handles special characters like 'ß' correctly.

        Args:
            mock_dspy_facade_factory: Factory function that produces a mock DspyFacade
            mock_dspy_facade: The mock DspyFacade instance
        """
        # Arrange
        input_text = "Straße"
        context = "This is a <rewrite>Straße</rewrite> context"
        options = TextRewriteOptions()

        # Mock the predict method to return a response with special characters
        mock_response = Mock(spec=RewirteInfo)
        mock_response.rewritten_text = "Die große Straße"
        mock_dspy_facade.predict.return_value = mock_response

        service = TextRewriteService(dspy_facade_factory=mock_dspy_facade_factory)

        # Act
        result = service.rewrite_text(input_text, context, options)

        # Assert
        assert isinstance(result, Success)
        rewrite_result = result.unwrap()
        assert "ß" not in rewrite_result.rewritten_text
        assert "ss" in rewrite_result.rewritten_text
        assert rewrite_result.rewritten_text == "Die grosse Strasse"

    def test_rewrite_text_with_rewrite_tag_replacement(
        self, mock_dspy_facade_factory: Mock, mock_dspy_facade: Mock
    ) -> None:
        """
        Test that rewrite_text correctly replaces <rewrite> tags with the original text.

        Args:
            mock_dspy_facade_factory: Factory function that produces a mock DspyFacade
            mock_dspy_facade: The mock DspyFacade instance
        """
        # Arrange
        input_text = "Hello world"
        context = "This is a <rewrite>Hello world</rewrite> context"
        options = TextRewriteOptions()

        # Mock the predict method to return text with <rewrite> tags
        mock_response = Mock(spec=RewirteInfo)
        mock_response.rewritten_text = "<rewrite> is replaced"
        mock_dspy_facade.predict.return_value = mock_response

        service = TextRewriteService(dspy_facade_factory=mock_dspy_facade_factory)

        # Act
        result = service.rewrite_text(input_text, context, options)

        # Assert
        assert isinstance(result, Success)
        rewrite_result = result.unwrap()
        assert rewrite_result.rewritten_text == "Hello world is replaced"

    def test_rewrite_text_exception_handling(self, mock_dspy_facade_factory: Mock, mock_dspy_facade: Mock) -> None:
        """
        Test that rewrite_text properly handles exceptions using the @safe decorator.

        Args:
            mock_dspy_facade_factory: Factory function that produces a mock DspyFacade
            mock_dspy_facade: The mock DspyFacade instance
        """
        # Arrange
        input_text = "Hello world"
        context = "This is a context"
        options = TextRewriteOptions()

        # Mock the predict method to raise an exception
        mock_dspy_facade.predict.side_effect = Exception("API error")

        service = TextRewriteService(dspy_facade_factory=mock_dspy_facade_factory)

        # Act
        result = service.rewrite_text(input_text, context, options)

        # Assert
        assert isinstance(result, Failure)
        assert isinstance(result.failure(), Exception)
        assert str(result.failure()) == "API error"
