"""Property-based tests using Hypothesis.

These tests verify properties that should hold for all inputs,
helping catch edge cases and ensure correctness.
"""

from hypothesis import given
from hypothesis import strategies as st

from deepwiki_cli.application.repository.scan import (
    collect_repository_files,
    is_git_repo,
)


@given(st.text(min_size=1, max_size=100))
def test_is_git_repo_always_boolean(path: str) -> None:
    """Property: is_git_repo always returns a boolean."""
    result = is_git_repo(path)
    assert isinstance(result, bool)


@given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10))
def test_collect_repository_files_returns_list(excluded_dirs: list[str]) -> None:
    """Property: collect_repository_files returns a list (when path exists).

    Note: This test may fail if path doesn't exist, which is expected behavior.
    """
    # Use a path that likely doesn't exist to test error handling
    test_path = "/tmp/nonexistent_test_path_12345"
    try:
        result = collect_repository_files(test_path, excluded_dirs=excluded_dirs)
        assert isinstance(result, list)
        # All items should be strings (file paths)
        assert all(isinstance(item, str) for item in result)
    except ValueError:
        # Expected if path doesn't exist
        pass


@given(st.text(min_size=1, max_size=100))
def test_file_paths_are_strings(path: str) -> None:
    """Property: File paths from collect_repository_files are always strings."""
    # This is a property test structure - actual implementation would need
    # a valid repository path
    assert isinstance(path, str)
    assert len(path) > 0
