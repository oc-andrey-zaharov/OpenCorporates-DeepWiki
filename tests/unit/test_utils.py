#!/usr/bin/env python3
"""
Unit tests for api/cli/utils.py

Tests all utility functions including validation, parsing, formatting, and interactive functions.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Mock problematic imports before importing utils
sys.modules["simple_term_menu"] = MagicMock()
sys.modules["adalflow"] = MagicMock()
sys.modules["adalflow.utils"] = MagicMock()
sys.modules["click"] = MagicMock()

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from api.cli import utils


@pytest.mark.unit
class TestValidateGithubUrl:
    """Tests for validate_github_url function"""

    def test_valid_github_url(self):
        """Test valid GitHub URLs"""
        is_valid, owner, repo = utils.validate_github_url(
            "https://github.com/owner/repo"
        )
        assert is_valid is True
        assert owner == "owner"
        assert repo == "repo"

    def test_valid_github_url_with_git_suffix(self):
        """Test GitHub URL with .git suffix"""
        is_valid, owner, repo = utils.validate_github_url(
            "https://github.com/owner/repo.git"
        )
        assert is_valid is True
        assert owner == "owner"
        assert repo == "repo"

    def test_valid_github_url_with_trailing_slash(self):
        """Test GitHub URL with trailing slash"""
        is_valid, owner, repo = utils.validate_github_url(
            "https://github.com/owner/repo/"
        )
        assert is_valid is True
        assert owner == "owner"
        assert repo == "repo"

    def test_valid_github_url_with_path(self):
        """Test GitHub URL with additional path"""
        is_valid, owner, repo = utils.validate_github_url(
            "https://github.com/owner/repo/tree/main"
        )
        assert is_valid is True
        assert owner == "owner"
        assert repo == "repo"

    def test_invalid_url_no_scheme(self):
        """Test invalid URL without scheme"""
        is_valid, owner, repo = utils.validate_github_url("github.com/owner/repo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_url_no_netloc(self):
        """Test invalid URL without netloc"""
        is_valid, owner, repo = utils.validate_github_url("https:///owner/repo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_url_insufficient_parts(self):
        """Test URL with insufficient path parts"""
        is_valid, owner, repo = utils.validate_github_url("https://github.com/repo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_empty_string(self):
        """Test empty string"""
        is_valid, owner, repo = utils.validate_github_url("")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_malformed_url(self):
        """Test malformed URL"""
        is_valid, owner, repo = utils.validate_github_url("not-a-url")
        assert is_valid is False
        assert owner is None
        assert repo is None


@pytest.mark.unit
class TestValidateGithubShorthand:
    """Tests for validate_github_shorthand function"""

    def test_valid_shorthand(self):
        """Test valid shorthand format"""
        is_valid, owner, repo = utils.validate_github_shorthand("owner/repo")
        assert is_valid is True
        assert owner == "owner"
        assert repo == "repo"

    def test_valid_shorthand_with_hyphens(self):
        """Test shorthand with hyphens"""
        is_valid, owner, repo = utils.validate_github_shorthand("my-owner/my-repo")
        assert is_valid is True
        assert owner == "my-owner"
        assert repo == "my-repo"

    def test_valid_shorthand_with_dots(self):
        """Test shorthand with dots"""
        is_valid, owner, repo = utils.validate_github_shorthand("owner.name/repo.name")
        assert is_valid is True
        assert owner == "owner.name"
        assert repo == "repo.name"

    def test_valid_shorthand_single_char(self):
        """Test single character owner/repo"""
        is_valid, owner, repo = utils.validate_github_shorthand("a/b")
        assert is_valid is True
        assert owner == "a"
        assert repo == "b"

    def test_valid_shorthand_max_length(self):
        """Test maximum length owner/repo"""
        owner_39 = "a" * 39
        repo_100 = "b" * 100
        is_valid, owner, repo = utils.validate_github_shorthand(
            f"{owner_39}/{repo_100}"
        )
        assert is_valid is True
        assert owner == owner_39
        assert repo == repo_100

    def test_invalid_shorthand_too_long_owner(self):
        """Test owner exceeding max length"""
        owner_40 = "a" * 40
        is_valid, owner, repo = utils.validate_github_shorthand(f"{owner_40}/repo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_shorthand_too_long_repo(self):
        """Test repo exceeding max length"""
        repo_101 = "b" * 101
        is_valid, owner, repo = utils.validate_github_shorthand(f"owner/{repo_101}")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_shorthand_starts_with_hyphen(self):
        """Test shorthand starting with hyphen"""
        is_valid, owner, repo = utils.validate_github_shorthand("-owner/repo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_shorthand_ends_with_hyphen(self):
        """Test shorthand ending with hyphen"""
        is_valid, owner, repo = utils.validate_github_shorthand("owner-/repo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_shorthand_starts_with_dot(self):
        """Test shorthand starting with dot"""
        is_valid, owner, repo = utils.validate_github_shorthand(".owner/repo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_shorthand_ends_with_dot(self):
        """Test shorthand ending with dot"""
        is_valid, owner, repo = utils.validate_github_shorthand("owner./repo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_shorthand_no_slash(self):
        """Test shorthand without slash"""
        is_valid, owner, repo = utils.validate_github_shorthand("ownerrepo")
        assert is_valid is False
        assert owner is None
        assert repo is None

    def test_invalid_shorthand_multiple_slashes(self):
        """Test shorthand with multiple slashes"""
        is_valid, owner, repo = utils.validate_github_shorthand("owner/repo/sub")
        assert is_valid is False
        assert owner is None
        assert repo is None


@pytest.mark.unit
class TestValidateLocalPath:
    """Tests for validate_local_path function"""

    def test_valid_local_path(self, tmp_path):
        """Test valid local directory path"""
        test_dir = tmp_path / "test_repo"
        test_dir.mkdir()
        assert utils.validate_local_path(str(test_dir)) is True

    def test_invalid_local_path_file(self, tmp_path):
        """Test invalid path pointing to a file"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test")
        assert utils.validate_local_path(str(test_file)) is False

    def test_invalid_local_path_nonexistent(self):
        """Test nonexistent path"""
        assert utils.validate_local_path("/nonexistent/path/12345") is False

    def test_empty_string(self):
        """Test empty string"""
        assert utils.validate_local_path("") is False


@pytest.mark.unit
class TestParseRepositoryInput:
    """Tests for parse_repository_input function"""

    def test_parse_github_url(self):
        """Test parsing GitHub URL"""
        repo_type, repo_url, owner, repo_name = utils.parse_repository_input(
            "https://github.com/owner/repo"
        )
        assert repo_type == "github"
        assert repo_url == "https://github.com/owner/repo"
        assert owner == "owner"
        assert repo_name == "repo"

    def test_parse_github_shorthand(self):
        """Test parsing GitHub shorthand"""
        repo_type, repo_url, owner, repo_name = utils.parse_repository_input(
            "owner/repo"
        )
        assert repo_type == "github"
        assert repo_url == "https://github.com/owner/repo"
        assert owner == "owner"
        assert repo_name == "repo"

    def test_parse_local_path(self, tmp_path):
        """Test parsing local path"""
        test_dir = tmp_path / "my_repo"
        test_dir.mkdir()
        repo_type, repo_url, owner, repo_name = utils.parse_repository_input(
            str(test_dir)
        )
        assert repo_type == "local"
        assert repo_url == str(test_dir)
        assert owner is None
        assert repo_name == "my_repo"

    def test_parse_invalid_input(self):
        """Test parsing invalid input"""
        with pytest.raises(ValueError, match="Invalid repository input"):
            utils.parse_repository_input("invalid-input")


@pytest.mark.unit
class TestFormatFileSize:
    """Tests for format_file_size function"""

    def test_format_bytes(self):
        """Test formatting bytes"""
        assert utils.format_file_size(0) == "0.0 B"
        assert utils.format_file_size(512) == "512.0 B"
        assert utils.format_file_size(1023) == "1023.0 B"

    def test_format_kilobytes(self):
        """Test formatting kilobytes"""
        assert utils.format_file_size(1024) == "1.0 KB"
        assert utils.format_file_size(1536) == "1.5 KB"
        assert utils.format_file_size(10240) == "10.0 KB"

    def test_format_megabytes(self):
        """Test formatting megabytes"""
        assert utils.format_file_size(1024 * 1024) == "1.0 MB"
        assert utils.format_file_size(1024 * 1024 * 2.5) == "2.5 MB"

    def test_format_gigabytes(self):
        """Test formatting gigabytes"""
        assert utils.format_file_size(1024 * 1024 * 1024) == "1.0 GB"
        assert utils.format_file_size(1024 * 1024 * 1024 * 5) == "5.0 GB"

    def test_format_terabytes(self):
        """Test formatting terabytes"""
        assert utils.format_file_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"
        assert utils.format_file_size(1024 * 1024 * 1024 * 1024 * 2) == "2.0 TB"


@pytest.mark.unit
class TestGetCachePath:
    """Tests for get_cache_path function"""

    @patch("adalflow.utils.get_adalflow_default_root_path")
    def test_get_cache_path(self, mock_get_path):
        """Test getting cache path"""
        mock_get_path.return_value = "/home/user/.adalflow"
        cache_path = utils.get_cache_path()
        assert isinstance(cache_path, Path)
        assert str(cache_path) == "/home/user/.adalflow/wikicache"


@pytest.mark.unit
class TestEnsureCacheDir:
    """Tests for ensure_cache_dir function"""

    @patch("api.cli.utils.get_cache_path")
    def test_ensure_cache_dir_creates_directory(self, mock_get_path, tmp_path):
        """Test that ensure_cache_dir creates directory if it doesn't exist"""
        cache_dir = tmp_path / "wikicache"
        mock_get_path.return_value = cache_dir
        utils.ensure_cache_dir()
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    @patch("api.cli.utils.get_cache_path")
    def test_ensure_cache_dir_existing_directory(self, mock_get_path, tmp_path):
        """Test that ensure_cache_dir doesn't fail if directory exists"""
        cache_dir = tmp_path / "wikicache"
        cache_dir.mkdir(parents=True)
        mock_get_path.return_value = cache_dir
        utils.ensure_cache_dir()
        assert cache_dir.exists()
        assert cache_dir.is_dir()


@pytest.mark.unit
class TestSelectFromList:
    """Tests for select_from_list function"""

    def test_select_from_list_empty_choices(self):
        """Test select_from_list with empty choices"""
        with pytest.raises(ValueError, match="No choices provided"):
            utils.select_from_list("Select", [])

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", False)
    @patch("click.prompt")
    @patch("click.echo")
    def test_select_from_list_fallback_mode(self, mock_echo, mock_prompt):
        """Test select_from_list in fallback mode"""
        mock_prompt.return_value = "option1"
        result = utils.select_from_list("Select", ["option1", "option2"])
        assert result == "option1"
        mock_prompt.assert_called_once()

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", False)
    @patch("click.prompt")
    @patch("click.echo")
    def test_select_from_list_fallback_with_custom(self, mock_echo, mock_prompt):
        """Test select_from_list with custom input allowed"""
        mock_prompt.return_value = "custom_value"
        result = utils.select_from_list(
            "Select", ["option1", "option2"], allow_custom=True
        )
        assert result == "custom_value"

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", True)
    @patch("api.cli.utils.TerminalMenu")
    def test_select_from_list_with_menu(self, mock_terminal_menu):
        """Test select_from_list with terminal menu"""
        mock_menu_instance = MagicMock()
        mock_menu_instance.show.return_value = 0
        mock_terminal_menu.return_value = mock_menu_instance

        result = utils.select_from_list("Select", ["option1", "option2"])
        assert result == "option1"
        mock_terminal_menu.assert_called_once()

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", True)
    @patch("api.cli.utils.TerminalMenu")
    @patch("click.prompt")
    @patch("click.echo")
    def test_select_from_list_custom_option(
        self, mock_echo, mock_prompt, mock_terminal_menu
    ):
        """Test select_from_list with custom option selected"""
        mock_menu_instance = MagicMock()
        mock_menu_instance.show.return_value = 2  # Custom option index
        mock_terminal_menu.return_value = mock_menu_instance
        mock_prompt.return_value = "custom_input"

        result = utils.select_from_list(
            "Select", ["option1", "option2"], allow_custom=True
        )
        assert result == "custom_input"
        mock_prompt.assert_called_once()


@pytest.mark.unit
class TestConfirmAction:
    """Tests for confirm_action function"""

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", False)
    @patch("click.confirm")
    def test_confirm_action_fallback_yes(self, mock_confirm):
        """Test confirm_action in fallback mode with yes"""
        mock_confirm.return_value = True
        result = utils.confirm_action("Confirm?", default=True)
        assert result is True
        mock_confirm.assert_called_once_with("Confirm?", default=True)

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", False)
    @patch("click.confirm")
    def test_confirm_action_fallback_no(self, mock_confirm):
        """Test confirm_action in fallback mode with no"""
        mock_confirm.return_value = False
        result = utils.confirm_action("Confirm?", default=False)
        assert result is False

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", True)
    @patch("api.cli.utils.TerminalMenu")
    def test_confirm_action_with_menu_yes(self, mock_terminal_menu):
        """Test confirm_action with menu selecting yes"""
        mock_menu_instance = MagicMock()
        mock_menu_instance.show.return_value = 0  # Yes index
        mock_terminal_menu.return_value = mock_menu_instance

        result = utils.confirm_action("Confirm?", default=True)
        assert result is True

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", True)
    @patch("api.cli.utils.TerminalMenu")
    def test_confirm_action_with_menu_no(self, mock_terminal_menu):
        """Test confirm_action with menu selecting no"""
        mock_menu_instance = MagicMock()
        mock_menu_instance.show.return_value = 1  # No index
        mock_terminal_menu.return_value = mock_menu_instance

        result = utils.confirm_action("Confirm?", default=False)
        assert result is False


@pytest.mark.unit
class TestSelectWikiFromList:
    """Tests for select_wiki_from_list function"""

    def test_select_wiki_from_list_empty(self):
        """Test select_wiki_from_list with empty list"""
        with pytest.raises(ValueError, match="No wikis provided"):
            utils.select_wiki_from_list([])

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", False)
    @patch("click.prompt")
    @patch("click.echo")
    def test_select_wiki_from_list_fallback(self, mock_echo, mock_prompt):
        """Test select_wiki_from_list in fallback mode"""
        wikis = [{"index": 1, "name": "Wiki1"}, {"index": 2, "name": "Wiki2"}]
        mock_prompt.return_value = 1
        result = utils.select_wiki_from_list(wikis)
        assert result == wikis[0]

    @patch("api.cli.utils.SIMPLE_TERM_MENU_AVAILABLE", True)
    @patch("api.cli.utils.TerminalMenu")
    def test_select_wiki_from_list_with_menu(self, mock_terminal_menu):
        """Test select_wiki_from_list with terminal menu"""
        wikis = [
            {"index": 1, "name": "Wiki1", "repo_type": "github"},
            {"index": 2, "name": "Wiki2", "repo_type": "local"},
        ]
        mock_menu_instance = MagicMock()
        mock_menu_instance.show.return_value = 1
        mock_terminal_menu.return_value = mock_menu_instance

        result = utils.select_wiki_from_list(wikis)
        assert result == wikis[1]
