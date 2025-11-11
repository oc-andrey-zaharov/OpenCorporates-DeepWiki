"""Tests for shared repository scanning helpers."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from api.utils.repo_scanner import collect_repository_files

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_collect_repository_files_respects_gitignore(tmp_path: Path) -> None:
    """Ensure .gitignore patterns are honored when walking the tree."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("ignored.txt\n*.log\n", encoding="utf-8")

    keep_file = repo / "keep.py"
    keep_file.write_text("print('ok')", encoding="utf-8")
    ignored_txt = repo / "ignored.txt"
    ignored_txt.write_text("skip me", encoding="utf-8")
    ignored_log = repo / "something.log"
    ignored_log.write_text("junk", encoding="utf-8")

    files = collect_repository_files(str(repo))
    assert str(keep_file) in files
    assert str(ignored_txt) not in files
    assert str(ignored_log) not in files


@pytest.mark.unit
def test_collect_repository_files_prefers_git_ls_files(tmp_path: Path) -> None:
    """When git metadata is available, only tracked files should be returned."""
    git_path = shutil.which("git")
    if git_path is None:
        pytest.skip("git executable not available")

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run([git_path, "init"], cwd=repo, check=True, capture_output=True)

    tracked = repo / "tracked.py"
    tracked.write_text("print('tracked')", encoding="utf-8")
    subprocess.run([git_path, "add", tracked.name], cwd=repo, check=True)
    subprocess.run(
        [git_path, "commit", "-m", "add tracked"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    untracked = repo / "untracked.py"
    untracked.write_text("print('tmp')", encoding="utf-8")

    files = collect_repository_files(str(repo))
    assert str(tracked) in files
    assert str(untracked) not in files
