import pytest
from pytest_mock import MockerFixture

from text_mate_backend.services.language_tool_service import LanguageToolService
from text_mate_backend.utils.configuration import Configuration


@pytest.fixture
def mock_config(mocker: MockerFixture) -> Configuration:
    """
    Provides a mock Configuration object for testing.

    Args:
        mocker: The pytest-mock fixture

    Returns:
        A mock Configuration object with test values
    """
    config = mocker.Mock(spec=Configuration)
    config.language_tool_api_url = "http://localhost:8010"
    return config


@pytest.fixture
def mock_language_tool_service(mocker: MockerFixture) -> LanguageToolService:
    """
    Provides a mock LanguageToolService for testing.

    Args:
        mocker: The pytest-mock fixture

    Returns:
        A mock LanguageToolService object
    """
    return mocker.Mock(spec=LanguageToolService)
