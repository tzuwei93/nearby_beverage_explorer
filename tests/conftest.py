import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_context():
    """Fixture providing a mock Lambda context"""
    context = Mock()
    context.aws_request_id = 'test-request-id'
    return context

@pytest.fixture
def mock_env_vars():
    """Fixture providing test environment variables"""
    return {
        'GOOGLE_MAPS_API_KEY': 'test_api_key',
        'S3_BUCKET': 'test-bucket',
        'RAW_DATA_PREFIX': 'raw/',
        'LOCATION_LAT': '25.041171',
        'LOCATION_LNG': '121.565227',
        'SEARCH_RADIUS': '1000'
    }
