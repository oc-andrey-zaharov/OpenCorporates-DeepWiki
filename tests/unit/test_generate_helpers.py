"""Tests for helper utilities in the generate CLI command."""

from deepwiki_cli.cli.commands.generate import _has_repo_changes


def test_has_repo_changes_true_when_any_lists_populated() -> None:
    """Ensure helper returns True if any change bucket is non-empty."""
    summary = {
        "changed_files": ["src/foo.py"],
        "new_files": [],
        "deleted_files": [],
    }
    assert _has_repo_changes(summary)


def test_has_repo_changes_false_when_all_buckets_empty() -> None:
    """Helper should return False when no files changed/new/deleted."""
    summary = {
        "changed_files": [],
        "new_files": [],
        "deleted_files": [],
    }
    assert not _has_repo_changes(summary)


def test_has_repo_changes_default_true_for_missing_summary() -> None:
    """Fallback to True when summary info is unavailable."""
    assert _has_repo_changes(None)
