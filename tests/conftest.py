import pytest
from pytest_mock import MockerFixture

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
    return config
