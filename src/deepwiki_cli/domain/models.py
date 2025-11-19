"""Pydantic models for DeepWiki.

This module contains all shared data models used across the application,
including wiki structures, cache data, and repository information.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RepoSnapshotFile(BaseModel):
    """Metadata about a single file referenced by a wiki cache snapshot."""

    path: str
    hash: str | None = None
    size: int | None = None
    modified_at: float | None = None


class RepoSnapshot(BaseModel):
    """Lightweight snapshot of repository files for change detection."""

    captured_at: float
    files: dict[str, RepoSnapshotFile]
    source: str | None = None
    reference: str | None = None


class WikiPage(BaseModel):
    """Model for a wiki page."""

    id: str
    title: str
    content: str
    filePaths: list[str]
    importance: str  # Should ideally be Literal['high', 'medium', 'low']
    relatedPages: list[str]
    metadata: dict[str, Any] | None = None




class RepoInfo(BaseModel):
    """Model for repository information."""

    owner: str
    repo: str
    type: str
    token: str | None = None
    localPath: str | None = None
    repoUrl: str | None = None


class WikiSection(BaseModel):
    """Model for the wiki sections."""

    id: str
    title: str
    pages: list[str]
    subsections: list[str] | None = None


class WikiStructureModel(BaseModel):
    """Model for the overall wiki structure."""

    id: str
    title: str
    description: str
    pages: list[WikiPage]
    sections: list[WikiSection] | None = None
    rootSections: list[str] | None = None


class WikiCacheData(BaseModel):
    """Model for the data to be stored in the wiki cache."""

    wiki_structure: WikiStructureModel
    generated_pages: dict[str, WikiPage]
    repo_url: str | None = None  # compatible for old cache
    repo: RepoInfo | None = None
    provider: str | None = None
    model: str | None = None
    version: int | None = 1
    created_at: str | None = None
    updated_at: str | None = None
    repo_snapshot: RepoSnapshot | None = None
    comprehensive: bool | None = None  # True for comprehensive, False for concise






__all__ = [
    "RepoInfo",
    "RepoSnapshot",
    "RepoSnapshotFile",
    "WikiCacheData",
    "WikiPage",
    "WikiSection",
    "WikiStructureModel",
]

