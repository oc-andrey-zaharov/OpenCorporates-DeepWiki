"""Integration tests for server mode functionality.

These tests verify that the CLI works correctly when connecting to
a FastAPI server for shared resources and caching.
"""

import pytest
import requests


class TestServerMode:
    """Test server mode functionality."""

    def test_server_health_check(self) -> None:
        """Test server health check endpoint.

        Requires server to be running on localhost:8001
        Run manually with server started.
        """
        try:
            response = requests.get("http://localhost:8001/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data
            assert data["service"] == "deepwiki-api"
        except requests.exceptions.ConnectionError:
            pytest.skip(
                "Server not running on localhost:8001. Start with 'make dev/backend'",
            )

    def test_wiki_generation_via_server(self) -> None:
        """Test wiki generation via server endpoint.

        This test requires:
        - Server running on localhost:8001
        - Valid API keys configured
        - Network access

        Run manually with server started.
        """
        # Check if server is running
        try:
            response = requests.get("http://localhost:8001/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Server not healthy. Start with 'make dev/backend'")
        except requests.exceptions.ConnectionError:
            pytest.skip(
                "Server not running on localhost:8001. Start with 'make dev/backend'",
            )

        # TODO: Implement actual wiki generation test via server endpoint
        # This would test actual wiki generation via server

    def test_server_mode_config(self) -> None:
        """Test server mode configuration."""
        from api.cli.config import load_config

        config = load_config()
        # Verify server mode config keys exist (if configured)
        # These may not be present in default config
        # Just verify config is loadable, don't require specific keys
        assert isinstance(config, dict)
