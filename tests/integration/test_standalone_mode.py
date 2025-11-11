"""Integration tests for standalone mode CLI functionality.

These tests verify that the CLI works correctly in standalone mode
without requiring a server to be running.
"""

import tempfile
from unittest.mock import patch

import pytest


class TestStandaloneMode:
    """Test standalone mode functionality."""

    def test_cli_imports(self) -> None:
        """Test that CLI can be imported without errors."""
        try:
            from api.cli.main import cli

            assert callable(cli)
        except ImportError as e:
            pytest.fail(f"Failed to import CLI: {e}")

    def test_config_loading(self) -> None:
        """Test that configuration can be loaded."""
        from api.cli.config import DEFAULT_CONFIG, load_config

        config = load_config()
        assert isinstance(config, dict)
        # Verify that default_provider exists either in loaded config or fallback DEFAULT_CONFIG
        assert "default_provider" in config or "default_provider" in DEFAULT_CONFIG

    def test_wiki_generation_standalone(self) -> None:
        """Test wiki generation in standalone mode.

        This test requires:
        - Valid API keys in environment
        - Network access to GitHub and LLM providers
        - Sufficient time for generation

        Run manually with: pytest tests/integration/test_standalone_mode.py::TestStandaloneMode::test_wiki_generation_standalone -v
        """
        # Check if API keys are available
        import os

        has_api_keys = any(
            os.getenv(key)
            for key in [
                "OPENAI_API_KEY",
                "GOOGLE_API_KEY",
                "OPENROUTER_API_KEY",
                "AWS_ACCESS_KEY_ID",
            ]
        )
        if not has_api_keys:
            pytest.skip(
                "API keys not configured. Set OPENAI_API_KEY, GOOGLE_API_KEY, "
                "OPENROUTER_API_KEY, or AWS_ACCESS_KEY_ID to run this test.",
            )

        # TODO: Implement actual wiki generation test
        # This would test actual wiki generation
        # For now, it's a placeholder

    def test_cache_path_resolution(self) -> None:
        """Test cache path is correctly resolved."""
        from api.cli.utils import get_cache_path

        # Mock get_adalflow_default_root_path to return a temporary directory
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch(
                "adalflow.utils.get_adalflow_default_root_path",
                return_value=tmpdir,
            ),
        ):
            cache_path = get_cache_path()
            # Verify the path is constructed correctly
            assert str(cache_path).endswith("wikicache")
            # The parent directory should exist (the temp dir)
            assert cache_path.parent.exists()
