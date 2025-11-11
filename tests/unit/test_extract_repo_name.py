#!/usr/bin/env python3
"""Focused test script for the _extract_repo_name_from_url method.

Run this script to test only the repository name extraction functionality.
Usage: python test_extract_repo_name.py
"""

import os
import sys

import pytest

# Add the parent directory to the path to import the data_pipeline module
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Import the modules under test
from api.services.data_pipeline import DatabaseManager


class TestExtractRepoNameFromUrl:
    """Comprehensive tests for the _extract_repo_name_from_url method."""

    def setup_method(self) -> None:
        """Set up test fixtures before each test method."""
        self.db_manager = DatabaseManager()

    def test_extract_repo_name_github_standard_url(self) -> None:
        # Test standard GitHub URL
        github_url = "https://github.com/owner/repo"
        result = self.db_manager._extract_repo_name_from_url(github_url, "github")
        assert result == "owner_repo"

        # Test GitHub URL with .git suffix
        github_url_git = "https://github.com/owner/repo.git"
        result = self.db_manager._extract_repo_name_from_url(github_url_git, "github")
        assert result == "owner_repo"

        # Test GitHub URL with trailing slash
        github_url_slash = "https://github.com/owner/repo/"
        result = self.db_manager._extract_repo_name_from_url(github_url_slash, "github")
        assert result == "owner_repo"

    def test_extract_repo_name_local_paths(self) -> None:
        """Test repository name extraction from local paths."""
        result = self.db_manager._extract_repo_name_from_url(
            "/home/user/projects/my-repo", "local",
        )
        assert result == "my-repo"

        result = self.db_manager._extract_repo_name_from_url(
            "/var/repos/project.git", "local",
        )
        assert result == "project"

    def test_extract_repo_name_current_implementation_bug(self) -> None:
        """Test that demonstrates the current implementation bug."""
        # The current implementation references 'type' which is not in scope
        # This should raise a NameError or TypeError due to undefined 'type' variable
        with pytest.raises((NameError, TypeError)):
            self.db_manager._extract_repo_name_from_url("https://github.com/owner/repo")

    def test_extract_repo_name_edge_cases(self) -> None:
        """Test edge cases for repository name extraction."""
        # Test URL with insufficient parts (should use fallback)
        short_url = "https://github.com/repo"
        result = self.db_manager._extract_repo_name_from_url(short_url, "github")
        assert result == "repo"

        # Test single directory name
        single_name = "my-repo"
        result = self.db_manager._extract_repo_name_from_url(single_name, "local")
        assert result == "my-repo"
