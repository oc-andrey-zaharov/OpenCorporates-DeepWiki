"""Repository-aware file collection helpers shared between CLI and services."""

from __future__ import annotations

import fnmatch
import logging
import os
import subprocess
from typing import Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Directories we never traverse
DEFAULT_EXCLUDED_DIRS = {".git", "vendor"}


def is_git_repo(path: str) -> bool:
    """Return True when the given path looks like a git repository."""
    git_dir = os.path.join(path, ".git")
    return os.path.exists(git_dir) or os.path.isdir(git_dir)


def _load_gitignore_patterns(repo_path: str) -> List[str]:
    """Load raw patterns from the repo's .gitignore file (if present)."""
    patterns: List[str] = []
    gitignore_path = os.path.join(repo_path, ".gitignore")

    if not os.path.exists(gitignore_path):
        return patterns

    try:
        with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                entry = line.strip()
                if entry and not entry.startswith("#"):
                    patterns.append(entry)
    except OSError as exc:
        logger.warning("Failed to read %s: %s", gitignore_path, exc)

    return patterns


def _matches_gitignore_pattern(
    file_path: str, patterns: Sequence[str], repo_path: str
) -> bool:
    """Return True if ``file_path`` matches any of the provided .gitignore rules."""
    rel_path = os.path.relpath(file_path, repo_path)
    rel_parts = rel_path.split(os.sep)

    for pattern in patterns:
        if not pattern:
            continue
        # Skip negated patterns for now – tooling uses positive excludes only
        if pattern.startswith("!"):
            continue

        normalized_pattern = pattern

        # Handle root anchored patterns
        if normalized_pattern.startswith("/"):
            normalized_pattern = normalized_pattern[1:]
            if fnmatch.fnmatch(rel_path, normalized_pattern) or fnmatch.fnmatch(
                rel_parts[0], normalized_pattern
            ):
                return True
            continue

        if normalized_pattern.endswith("/"):
            normalized_pattern = normalized_pattern[:-1]
            for part in rel_parts[:-1]:
                # Support ** wildcards for directories by normalizing to *
                candidate = normalized_pattern.replace("**", "*")
                if fnmatch.fnmatch(part, candidate):
                    return True
            continue

        if "**" in normalized_pattern:
            candidate = normalized_pattern.replace("**", "*")
            if fnmatch.fnmatch(rel_path, candidate):
                return True
            continue

        if fnmatch.fnmatch(rel_path, normalized_pattern) or fnmatch.fnmatch(
            os.path.basename(rel_path), normalized_pattern
        ):
            return True

    return False


def _collect_files_with_git(
    repo_path: str, *, excluded_dirs: Iterable[str]
) -> Optional[List[str]]:
    """Prefer ``git ls-files`` for speed/accuracy whenever possible."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as exc:
        logger.warning("git ls-files failed (%s); falling back to os.walk", exc)
        return None

    files: List[str] = []
    for line in result.stdout.splitlines():
        relative = line.strip()
        if not relative:
            continue
        full_path = os.path.join(repo_path, relative)
        if not os.path.isfile(full_path):
            continue
        rel_parts = os.path.relpath(full_path, repo_path).split(os.sep)
        if any(part in excluded_dirs for part in rel_parts):
            continue
        files.append(full_path)
    return files


def _collect_files_with_walk(
    repo_path: str, *, excluded_dirs: Iterable[str]
) -> List[str]:
    """Fallback collector that walks the filesystem while honoring .gitignore."""
    files: List[str] = []
    patterns = _load_gitignore_patterns(repo_path)

    for root, dirs, filenames in os.walk(repo_path):
        # Prevent descending into excluded directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        rel_root = os.path.relpath(root, repo_path)
        if rel_root != ".":
            parts = rel_root.split(os.sep)
            if any(part in excluded_dirs for part in parts):
                continue

        for filename in filenames:
            file_path = os.path.join(root, filename)
            rel_parts = os.path.relpath(file_path, repo_path).split(os.sep)
            if any(part in excluded_dirs for part in rel_parts):
                continue
            if patterns and _matches_gitignore_pattern(file_path, patterns, repo_path):
                continue
            files.append(file_path)

    return files


def collect_repository_files(
    repo_path: str,
    *,
    excluded_dirs: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Collect files for ``repo_path`` using git metadata (when available) or a walk.

    Args:
        repo_path: location of the repository.
        excluded_dirs: Additional directory names to skip everywhere in the tree.

    Returns:
        Absolute file paths suitable for downstream processing.
    """
    if not os.path.isdir(repo_path):
        raise ValueError(f"Repository path does not exist: {repo_path}")

    combined_excludes = set(DEFAULT_EXCLUDED_DIRS)
    if excluded_dirs:
        combined_excludes.update(excluded_dirs)

    if is_git_repo(repo_path):
        files = _collect_files_with_git(repo_path, excluded_dirs=combined_excludes)
        if files is not None:
            logger.info("Collected %d files via git ls-files", len(files))
            return files

    files = _collect_files_with_walk(repo_path, excluded_dirs=combined_excludes)
    logger.info("Collected %d files via directory walk", len(files))
    return files


__all__ = ["collect_repository_files", "is_git_repo", "DEFAULT_EXCLUDED_DIRS"]
