#!/usr/bin/env python3
"""Unit tests for api/cli/config.py.

Tests configuration management functions including loading, saving, and accessing config values.
"""

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add the parent directory to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from deepwiki_cli.cli import config


@pytest.mark.unit
class TestEnsureConfigDir:
    """Tests for ensure_config_dir function."""

    @patch.object(config, "CONFIG_DIR")
    def test_ensure_config_dir_creates_directory(
        self,
        mock_config_dir: MagicMock,
    ) -> None:
        """Test that ensure_config_dir creates directory if it doesn't exist."""
        mock_config_dir.mkdir = MagicMock()
        config.ensure_config_dir()
        mock_config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)


@pytest.mark.unit
class TestDeepMerge:
    """Tests for _deep_merge function."""

    def test_deep_merge_simple(self) -> None:
        """Test simple dictionary merge."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = config._deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}
        # Original should not be modified
        assert base == {"a": 1, "b": 2}

    def test_deep_merge_nested(self) -> None:
        """Test nested dictionary merge."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}, "b": 4}
        result = config._deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 4}

    def test_deep_merge_override_with_non_dict(self) -> None:
        """Test that non-dict values override dict values."""
        base = {"a": {"x": 1}}
        override = {"a": "string"}
        result = config._deep_merge(base, override)
        assert result == {"a": "string"}

    def test_deep_merge_empty_base(self) -> None:
        """Test merge with empty base."""
        base = {}
        override = {"a": 1, "b": 2}
        result = config._deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_deep_merge_empty_override(self) -> None:
        """Test merge with empty override."""
        base = {"a": 1, "b": 2}
        override = {}
        result = config._deep_merge(base, override)
        assert result == {"a": 1, "b": 2}


@pytest.mark.unit
class TestLoadConfig:
    """Tests for load_config function."""

    @patch.object(config, "CONFIG_FILE")
    def test_load_config_file_not_exists(self, mock_config_file: MagicMock) -> None:
        """Test loading config when file doesn't exist."""
        # Mock the exists() method to return False
        mock_config_file.exists.return_value = False
        result = config.load_config()
        # Should return default config when file doesn't exist
        assert isinstance(result, dict)
        assert "default_provider" in result
        assert "wiki_workspace" in result
        # Verify exists() was called
        mock_config_file.exists.assert_called_once()

    @patch.object(config, "CONFIG_FILE")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"wiki_workspace": "custom/wiki"}',
    )
    def test_load_config_file_exists(
        self,
        mock_file: Any,
        mock_config_file: MagicMock,
    ) -> None:
        """Test loading config from existing file."""
        mock_config_file.exists.return_value = True

        result = config.load_config()

        assert result["wiki_workspace"] == "custom/wiki"
        # Should merge with defaults
        assert "default_provider" in result

    @patch.object(config, "CONFIG_FILE")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"file_filters": {"excluded_dirs": ["test"]}}',
    )
    def test_load_config_deep_merge(
        self,
        mock_file: Any,
        mock_config_file: MagicMock,
    ) -> None:
        """Test that config is deep merged with defaults."""
        mock_config_file.exists.return_value = True

        result = config.load_config()

        assert result["file_filters"]["excluded_dirs"] == ["test"]
        assert "excluded_files" in result["file_filters"]  # From defaults

    @patch.object(config, "CONFIG_FILE")
    @patch("builtins.open")
    def test_load_config_file_error(
        self,
        mock_open: MagicMock,
        mock_config_file: MagicMock,
    ) -> None:
        """Test loading config when file read fails."""
        mock_config_file.exists.return_value = True
        mock_open.side_effect = OSError("Permission denied")

        result = config.load_config()
        assert result == config.DEFAULT_CONFIG.copy()


@pytest.mark.unit
class TestSaveConfig:
    """Tests for save_config function."""

    @patch.object(config, "ensure_config_dir")
    @patch.object(config, "CONFIG_FILE")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_config_success(
        self,
        mock_file: Any,
        mock_config_file: MagicMock,
        mock_ensure_dir: MagicMock,
    ) -> None:
        """Test successful config save."""
        config_data = {"wiki_workspace": "docs/wiki"}
        config.save_config(config_data)

        # Verify ensure_config_dir was called
        mock_ensure_dir.assert_called_once()
        # Verify file was opened for writing
        mock_file.assert_called_once_with(mock_config_file, "w")
        # Verify data was written
        handle = mock_file()
        assert handle.write.called
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        written_data = json.loads(written_content)
        assert written_data == config_data

    @patch.object(config, "ensure_config_dir")
    @patch.object(config, "CONFIG_FILE")
    @patch("builtins.open")
    def test_save_config_error(
        self,
        mock_open: MagicMock,
        mock_config_file: Any,
        mock_ensure_dir: Any,
    ) -> None:
        """Test config save with error."""
        mock_open.side_effect = OSError("Permission denied")

        with pytest.raises(IOError, match="Permission denied"):
            config.save_config({"test": "value"})


@pytest.mark.unit
class TestGetConfigValue:
    """Tests for get_config_value function."""

    @patch.object(config, "load_config")
    def test_get_config_value_simple_key(self, mock_load_config: MagicMock) -> None:
        """Test getting simple config value."""
        mock_load_config.return_value = {"wiki_workspace": "docs/wiki"}
        result = config.get_config_value("wiki_workspace")
        assert result == "docs/wiki"
        mock_load_config.assert_called_once()

    @patch.object(config, "load_config")
    def test_get_config_value_nested_key(self, mock_load_config: MagicMock) -> None:
        """Test getting nested config value."""
        mock_load_config.return_value = {
            "file_filters": {"excluded_dirs": ["test"], "excluded_files": []},
        }
        result = config.get_config_value("file_filters.excluded_dirs")
        assert result == ["test"]
        mock_load_config.assert_called_once()

    @patch.object(config, "load_config")
    def test_get_config_value_default(self, mock_load_config: MagicMock) -> None:
        """Test getting config value with default."""
        mock_load_config.return_value = {}
        result = config.get_config_value("nonexistent", default="default_value")
        assert result == "default_value"
        mock_load_config.assert_called_once()

    @patch.object(config, "load_config")
    def test_get_config_value_nonexistent_nested(
        self,
        mock_load_config: MagicMock,
    ) -> None:
        """Test getting nonexistent nested key."""
        mock_load_config.return_value = {"file_filters": {}}
        result = config.get_config_value("file_filters.nonexistent", default="default")
        assert result == "default"
        mock_load_config.assert_called_once()

    @patch.object(config, "load_config")
    def test_get_config_value_intermediate_not_dict(
        self,
        mock_load_config: MagicMock,
    ) -> None:
        """Test getting nested key when intermediate is not a dict."""
        mock_load_config.return_value = {"file_filters": "not_a_dict"}
        result = config.get_config_value(
            "file_filters.excluded_dirs",
            default="default",
        )
        # When intermediate is not a dict, isinstance(value, dict) is False
        # so it should return default immediately
        assert result == "default"
        # Verify load_config was called
        mock_load_config.assert_called_once()


@pytest.mark.unit
class TestSetConfigValue:
    """Tests for set_config_value function."""

    @patch.object(config, "save_config")
    @patch.object(config, "load_config")
    def test_set_config_value_simple_key(
        self,
        mock_load_config: MagicMock,
        mock_save_config: MagicMock,
    ) -> None:
        """Test setting simple config value."""
        initial_config = {"wiki_workspace": "docs/wiki"}
        mock_load_config.return_value = initial_config.copy()
        config.set_config_value("wiki_workspace", "docs/custom-wiki")

        # Verify load_config was called
        mock_load_config.assert_called_once()
        # Verify save_config was called with updated config
        mock_save_config.assert_called_once()
        saved_config = mock_save_config.call_args[0][0]
        assert saved_config["wiki_workspace"] == "docs/custom-wiki"

    @patch.object(config, "save_config")
    @patch.object(config, "load_config")
    def test_set_config_value_nested_key(
        self,
        mock_load_config: MagicMock,
        mock_save_config: MagicMock,
    ) -> None:
        """Test setting nested config value."""
        initial_config = {"file_filters": {"excluded_dirs": []}}
        mock_load_config.return_value = initial_config.copy()
        config.set_config_value("file_filters.excluded_dirs", ["test"])

        # Verify save_config was called
        mock_save_config.assert_called_once()
        saved_config = mock_save_config.call_args[0][0]
        assert saved_config["file_filters"]["excluded_dirs"] == ["test"]

    @patch.object(config, "save_config")
    @patch.object(config, "load_config")
    def test_set_config_value_new_nested_key(
        self,
        mock_load_config: MagicMock,
        mock_save_config: MagicMock,
    ) -> None:
        """Test setting new nested key."""
        mock_load_config.return_value = {}
        config.set_config_value("file_filters.excluded_dirs", ["test"])

        # Verify save_config was called
        mock_save_config.assert_called_once()
        saved_config = mock_save_config.call_args[0][0]
        assert saved_config["file_filters"]["excluded_dirs"] == ["test"]

    @patch.object(config, "save_config")
    @patch.object(config, "load_config")
    def test_set_config_value_type_error(
        self,
        mock_load_config: MagicMock,
        mock_save_config: Any,
    ) -> None:
        """Test setting nested key when intermediate is not a dict."""
        mock_load_config.return_value = {"file_filters": "not_a_dict"}

        with pytest.raises(TypeError, match="not a dictionary"):
            config.set_config_value("file_filters.excluded_dirs", ["test"])


@pytest.mark.unit
class TestGetProviderModels:
    """Tests for get_provider_models function."""

    @patch(
        "deepwiki_cli.config.configs",
        {
            "providers": {
                "google": {"models": {"model1": {}, "model2": {}}},
                "openai": {"models": {"model3": {}}},
            },
        },
    )
    def test_get_provider_models(self) -> None:
        """Test getting provider models."""
        result = config.get_provider_models()
        assert "google" in result
        assert "openai" in result
        assert result["google"] == ["model1", "model2"]
        assert result["openai"] == ["model3"]

    @patch("deepwiki_cli.config.configs", {})
    def test_get_provider_models_no_providers(self) -> None:
        """Test getting provider models when no providers exist."""
        result = config.get_provider_models()
        assert result == {}

    @patch("deepwiki_cli.config.configs", {"providers": {"google": {}}})
    def test_get_provider_models_no_models_key(self) -> None:
        """Test getting provider models when models key is missing."""
        result = config.get_provider_models()
        assert result == {}
