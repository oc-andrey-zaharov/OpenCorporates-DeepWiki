#!/usr/bin/env python3
"""Unit tests for api/utils/mode.py

Tests mode detection and server health checking functions.
"""

import sys

# Add the parent directory to the path
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import RequestException, Timeout

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.utils import mode


@pytest.mark.unit
class TestIsServerMode:
    """Tests for is_server_mode function"""

    @patch("api.utils.mode.load_config")
    def test_is_server_mode_true(self, mock_load_config):
        """Test when server mode is enabled"""
        mock_load_config.return_value = {"use_server": True}
        assert mode.is_server_mode() is True

    @patch("api.utils.mode.load_config")
    def test_is_server_mode_false(self, mock_load_config):
        """Test when server mode is disabled"""
        mock_load_config.return_value = {"use_server": False}
        assert mode.is_server_mode() is False

    @patch("api.utils.mode.load_config")
    def test_is_server_mode_default(self, mock_load_config):
        """Test when use_server key is missing"""
        mock_load_config.return_value = {}
        assert mode.is_server_mode() is False


@pytest.mark.unit
class TestGetServerUrl:
    """Tests for get_server_url function"""

    @patch("api.utils.mode.load_config")
    def test_get_server_url_configured(self, mock_load_config):
        """Test getting configured server URL"""
        mock_load_config.return_value = {"server_url": "http://example.com:8000"}
        assert mode.get_server_url() == "http://example.com:8000"

    @patch("api.utils.mode.load_config")
    def test_get_server_url_default(self, mock_load_config):
        """Test getting default server URL"""
        mock_load_config.return_value = {}
        assert mode.get_server_url() == "http://localhost:8001"


@pytest.mark.unit
class TestShouldFallback:
    """Tests for should_fallback function"""

    @patch("api.utils.mode.load_config")
    def test_should_fallback_true(self, mock_load_config):
        """Test when auto_fallback is enabled"""
        mock_load_config.return_value = {"auto_fallback": True}
        assert mode.should_fallback() is True

    @patch("api.utils.mode.load_config")
    def test_should_fallback_false(self, mock_load_config):
        """Test when auto_fallback is disabled"""
        mock_load_config.return_value = {"auto_fallback": False}
        assert mode.should_fallback() is False

    @patch("api.utils.mode.load_config")
    def test_should_fallback_default(self, mock_load_config):
        """Test when auto_fallback key is missing (defaults to True)"""
        mock_load_config.return_value = {}
        assert mode.should_fallback() is True


@pytest.mark.unit
class TestCheckServerHealth:
    """Tests for check_server_health function"""

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.requests.get")
    def test_check_server_health_success(self, mock_get, mock_get_url):
        """Test successful server health check"""
        mock_get_url.return_value = "http://localhost:8001"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = mode.check_server_health()
        assert result is True
        mock_get.assert_called_once_with("http://localhost:8001/", timeout=5)

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.requests.get")
    def test_check_server_health_custom_url(self, mock_get, mock_get_url):
        """Test server health check with custom URL"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = mode.check_server_health("http://custom:9000", timeout=10)
        assert result is True
        mock_get.assert_called_once_with("http://custom:9000/", timeout=10)

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.requests.get")
    def test_check_server_health_non_200(self, mock_get, mock_get_url):
        """Test server health check with non-200 status"""
        mock_get_url.return_value = "http://localhost:8001"
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = mode.check_server_health()
        assert result is False

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.requests.get")
    def test_check_server_health_connection_error(self, mock_get, mock_get_url):
        """Test server health check with connection error"""
        mock_get_url.return_value = "http://localhost:8001"
        mock_get.side_effect = RequestException("Connection failed")

        result = mode.check_server_health()
        assert result is False

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.requests.get")
    def test_check_server_health_timeout(self, mock_get, mock_get_url):
        """Test server health check with timeout"""
        mock_get_url.return_value = "http://localhost:8001"
        mock_get.side_effect = Timeout("Request timed out")

        result = mode.check_server_health()
        assert result is False


@pytest.mark.unit
class TestCheckServerHealthWithRetry:
    """Tests for check_server_health_with_retry function"""

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.check_server_health")
    def test_check_server_health_with_retry_success_first_attempt(
        self, mock_check_health, mock_get_url,
    ):
        """Test successful health check on first attempt"""
        mock_get_url.return_value = "http://localhost:8001"
        mock_check_health.return_value = True

        result = mode.check_server_health_with_retry()
        assert result is True
        mock_check_health.assert_called_once()

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.check_server_health")
    @patch("api.utils.mode.time.sleep")
    def test_check_server_health_with_retry_success_after_retries(
        self, mock_sleep, mock_check_health, mock_get_url,
    ):
        """Test successful health check after retries"""
        mock_get_url.return_value = "http://localhost:8001"
        mock_check_health.side_effect = [False, False, True]

        result = mode.check_server_health_with_retry(max_retries=3)
        assert result is True
        assert mock_check_health.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.check_server_health")
    @patch("api.utils.mode.time.sleep")
    def test_check_server_health_with_retry_all_fail(
        self, mock_sleep, mock_check_health, mock_get_url,
    ):
        """Test health check failure after all retries"""
        mock_get_url.return_value = "http://localhost:8001"
        mock_check_health.return_value = False

        result = mode.check_server_health_with_retry(max_retries=3)
        assert result is False
        assert mock_check_health.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @patch("api.utils.mode.get_server_url")
    @patch("api.utils.mode.check_server_health")
    @patch("api.utils.mode.time.sleep")
    def test_check_server_health_with_retry_exponential_backoff(
        self, mock_sleep, mock_check_health, mock_get_url,
    ):
        """Test exponential backoff timing"""
        mock_get_url.return_value = "http://localhost:8001"
        mock_check_health.return_value = False

        mode.check_server_health_with_retry(max_retries=4, initial_backoff=0.5)

        # Verify exponential backoff: 0.5, 1.0, 2.0
        expected_sleeps = [0.5, 1.0, 2.0]
        actual_sleeps = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_sleeps == expected_sleeps

    @patch("api.utils.mode.check_server_health")
    def test_check_server_health_with_retry_custom_url(self, mock_check_health):
        """Test retry with custom server URL"""
        mock_check_health.return_value = True

        result = mode.check_server_health_with_retry("http://custom:9000")
        assert result is True
        mock_check_health.assert_called_once_with("http://custom:9000", 5)
