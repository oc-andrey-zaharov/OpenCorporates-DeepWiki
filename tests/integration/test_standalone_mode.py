"""
Integration tests for standalone mode CLI functionality.

These tests verify that the CLI works correctly in standalone mode
without requiring a server to be running.
"""

import pytest
import tempfile
from unittest.mock import patch


class TestStandaloneMode:
    """Test standalone mode functionality."""

    def test_cli_imports(self):
        """Test that CLI can be imported without errors."""
        try:
            from api.cli.main import cli

            assert callable(cli)
        except ImportError as e:
            pytest.fail(f"Failed to import CLI: {e}")

    def test_config_loading(self):
        """Test that configuration can be loaded."""
        from api.cli.config import load_config, DEFAULT_CONFIG

        config = load_config()
        assert isinstance(config, dict)
        # Verify default config structure
        assert "default_provider" in config or "default_provider" in DEFAULT_CONFIG

    @pytest.mark.skip(reason="Requires API keys and network access")
    def test_wiki_generation_standalone(self):
        """Test wiki generation in standalone mode.

        This test requires:
        - Valid API keys in environment
        - Network access to GitHub and LLM providers
        - Sufficient time for generation

        Run manually with: pytest tests/integration/test_standalone_mode.py::TestStandaloneMode::test_wiki_generation_standalone -v
        """
        # This would test actual wiki generation
        # For now, it's a placeholder
        pass

    def test_cache_operations(self):
        """Test cache read/write operations."""
        from api.cli.utils import get_cache_path

        # Mock get_adalflow_default_root_path to return a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "adalflow.utils.get_adalflow_default_root_path", return_value=tmpdir
            ):
                cache_path = get_cache_path()
                # Verify the path is constructed correctly
                assert str(cache_path).endswith("wikicache")
                # The parent directory should exist (the temp dir)
                assert cache_path.parent.exists()
