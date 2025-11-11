"""Utilities for working with DeepWiki cache files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

CACHE_FILENAME_PREFIX = "deepwiki_cache_"
DEFAULT_LANGUAGE = "en"


def _sanitize_component(value: Optional[str]) -> str:
    """Normalize filename components to avoid filesystem issues."""

    if not value:
        return "unknown"
    return (
        value.strip().replace("/", "-").replace(" ", "-").replace(os.sep, "-")
    )


@dataclass
class CacheFileInfo:
    """Metadata returned when listing cache files."""

    path: Path
    repo_type: str
    owner: str
    repo: str
    language: str
    version: int
    modified: datetime
    size: int

    @property
    def display_name(self) -> str:
        if self.owner and self.owner != "local":
            return f"{self.owner}/{self.repo}"
        return self.repo


def get_cache_filename(
    repo_type: str,
    owner: Optional[str],
    repo_name: str,
    language: str = DEFAULT_LANGUAGE,
    version: Optional[int] = 1,
    suffix: Optional[str] = None,
) -> str:
    """Build a cache filename with optional versioning."""

    safe_type = _sanitize_component(repo_type or "github")
    safe_owner = _sanitize_component(owner or "local")
    safe_repo = _sanitize_component(repo_name)
    safe_language = _sanitize_component(language or DEFAULT_LANGUAGE)

    filename = f"{CACHE_FILENAME_PREFIX}{safe_type}_{safe_owner}_{safe_repo}_{safe_language}"
    if suffix:
        filename = f"{filename}_{_sanitize_component(suffix)}"
    if version and version > 1:
        filename = f"{filename}_v{version}"
    return f"{filename}.json"


def _parse_version_token(token: str) -> Optional[int]:
    if token and token.startswith("v") and token[1:].isdigit():
        return int(token[1:])
    return None


def parse_cache_filename(path: Path) -> Optional[Dict[str, str]]:
    """Extract metadata from a cache filename."""

    name = path.stem
    if not name.startswith(CACHE_FILENAME_PREFIX):
        return None

    payload = name[len(CACHE_FILENAME_PREFIX) :]
    parts = payload.split("_")
    if len(parts) < 4:
        return None

    version = _parse_version_token(parts[-1])
    if version is not None:
        parts = parts[:-1]
    else:
        version = 1

    if len(parts) < 4:
        return None

    language = parts[-1]
    repo_type = parts[0]
    owner = parts[1]
    repo = "_".join(parts[2:-1])

    return {
        "repo_type": repo_type,
        "owner": owner,
        "repo": repo,
        "language": language,
        "version": version,
    }


def list_existing_wikis(
    cache_dir: Path,
    repo_type: str,
    owner: Optional[str],
    repo_name: str,
) -> List[CacheFileInfo]:
    """Return cache files for a specific repository (all versions)."""

    if not cache_dir.exists():
        return []

    safe_type = _sanitize_component(repo_type or "github")
    safe_owner = _sanitize_component(owner or "local")
    safe_repo = _sanitize_component(repo_name)

    pattern = f"{CACHE_FILENAME_PREFIX}{safe_type}_{safe_owner}_{safe_repo}_*.json"

    entries: List[CacheFileInfo] = []
    for path in cache_dir.glob(pattern):
        meta = parse_cache_filename(path)
        if not meta:
            continue
        stats = path.stat()
        entries.append(
            CacheFileInfo(
                path=path,
                repo_type=meta["repo_type"],
                owner=meta["owner"],
                repo=meta["repo"],
                language=meta["language"],
                version=int(meta["version"]),
                modified=datetime.fromtimestamp(stats.st_mtime),
                size=stats.st_size,
            )
        )

    entries.sort(key=lambda e: (e.version, e.modified), reverse=True)
    return entries


__all__ = [
    "CacheFileInfo",
    "DEFAULT_LANGUAGE",
    "CACHE_FILENAME_PREFIX",
    "get_cache_filename",
    "list_existing_wikis",
    "parse_cache_filename",
]
