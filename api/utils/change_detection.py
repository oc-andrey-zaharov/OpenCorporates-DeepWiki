"""Change detection helpers for wiki regeneration."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from api.models import (
    RepoSnapshot,
    RepoSnapshotFile,
    WikiCacheData,
    WikiStructureModel,
)

logger = logging.getLogger(__name__)


def _hash_file(path: str, chunk_size: int = 65536) -> Optional[str]:
    """Compute a sha256 hash for a file, handling errors gracefully."""

    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        logger.debug(f"Failed to hash {path}: {exc}")
        return None


def build_snapshot_from_local(repo_path: str, files: List[str]) -> RepoSnapshot:
    """Create a repository snapshot from local files."""

    snapshot_files: Dict[str, RepoSnapshotFile] = {}
    for absolute_path in files:
        try:
            rel_path = os.path.relpath(absolute_path, repo_path)
        except ValueError:
            rel_path = absolute_path

        try:
            stats = os.stat(absolute_path)
        except OSError as exc:
            logger.debug(f"Unable to stat {absolute_path}: {exc}")
            continue

        snapshot_files[rel_path] = RepoSnapshotFile(
            path=rel_path,
            size=stats.st_size,
            modified_at=stats.st_mtime,
            hash=_hash_file(absolute_path),
        )

    return RepoSnapshot(
        captured_at=time.time(),
        files=snapshot_files,
        source="local",
        reference=repo_path,
    )


def build_snapshot_from_tree(
    tree_entries: Optional[List[Dict[str, str]]],
    reference: Optional[str] = None,
) -> RepoSnapshot:
    """Create a snapshot from GitHub tree metadata."""

    snapshot_files: Dict[str, RepoSnapshotFile] = {}
    if tree_entries:
        for entry in tree_entries:
            path = entry.get("path")
            if not path or entry.get("type") not in {None, "blob"}:
                continue
            snapshot_files[path] = RepoSnapshotFile(
                path=path,
                hash=entry.get("sha"),
                size=entry.get("size"),
            )

    return RepoSnapshot(
        captured_at=time.time(),
        files=snapshot_files,
        source="github",
        reference=reference,
    )


def load_existing_cache(cache_file: Path) -> Optional[WikiCacheData]:
    """Load cache data from disk safely."""

    if not cache_file or not cache_file.exists():
        return None

    try:
        with cache_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return WikiCacheData(**data)
    except Exception as exc:
        logger.warning(f"Failed to load cache from {cache_file}: {exc}")
        return None


def _file_changed(previous: RepoSnapshotFile, current: RepoSnapshotFile) -> bool:
    if previous.hash and current.hash and previous.hash != current.hash:
        return True
    if (
        previous.size is not None
        and current.size is not None
        and previous.size != current.size
    ):
        return True
    if (
        previous.modified_at is not None
        and current.modified_at is not None
        and abs(previous.modified_at - current.modified_at) > 1
    ):
        return True
    return False


def detect_repo_changes(
    repo_path: Optional[str],
    existing_cache: Optional[WikiCacheData],
    current_snapshot: Optional[RepoSnapshot],
) -> Dict[str, List[str]]:
    """Compare snapshots and return change summary."""

    summary = {
        "changed_files": [],
        "new_files": [],
        "deleted_files": [],
        "unchanged_count": 0,
        "snapshot": current_snapshot,
    }

    if not current_snapshot or not existing_cache or not existing_cache.repo_snapshot:
        if current_snapshot:
            summary["new_files"] = sorted(current_snapshot.files.keys())
        return summary

    previous_snapshot = existing_cache.repo_snapshot
    previous_files = previous_snapshot.files or {}
    current_files = current_snapshot.files or {}

    for path, current_file in current_files.items():
        previous_file = previous_files.get(path)
        if not previous_file:
            summary["new_files"].append(path)
            continue
        if _file_changed(previous_file, current_file):
            summary["changed_files"].append(path)
        else:
            summary["unchanged_count"] += 1

    for path in previous_files.keys() - current_files.keys():
        summary["deleted_files"].append(path)

    summary["changed_files"].sort()
    summary["new_files"].sort()
    summary["deleted_files"].sort()
    return summary


def find_affected_pages(
    changed_files: List[str],
    wiki_structure: Optional[WikiStructureModel],
) -> List[str]:
    """Return page IDs whose file mappings intersect with changed files."""

    if not changed_files or not wiki_structure:
        return []

    changed_set = {path.strip() for path in changed_files if path}
    affected: List[str] = []

    for page in wiki_structure.pages:
        page_files = {fp.strip() for fp in page.filePaths}
        if page_files & changed_set:
            affected.append(page.id)

    return affected


__all__ = [
    "build_snapshot_from_local",
    "build_snapshot_from_tree",
    "detect_repo_changes",
    "find_affected_pages",
    "load_existing_cache",
]
