"""
Pydantic models for DeepWiki.

This module contains all shared data models used across the application,
including wiki structures, cache data, and repository information.
"""

from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field


class RepoSnapshotFile(BaseModel):
    """Metadata about a single file referenced by a wiki cache snapshot."""

    path: str
    hash: Optional[str] = None
    size: Optional[int] = None
    modified_at: Optional[float] = None


class RepoSnapshot(BaseModel):
    """Lightweight snapshot of repository files for change detection."""

    captured_at: float
    files: Dict[str, RepoSnapshotFile]
    source: Optional[str] = None
    reference: Optional[str] = None


class WikiPage(BaseModel):
    """
    Model for a wiki page.
    """

    id: str
    title: str
    content: str
    filePaths: List[str]
    importance: str  # Should ideally be Literal['high', 'medium', 'low']
    relatedPages: List[str]


class ProcessedProjectEntry(BaseModel):
    """
    Model for a processed project entry in the cache.
    """

    id: str  # Filename
    owner: str
    repo: str
    name: str  # owner/repo
    repo_type: str  # Renamed from type to repo_type for clarity with existing models
    submittedAt: int  # Timestamp
    language: str  # Extracted from filename


class RepoInfo(BaseModel):
    """
    Model for repository information.
    """

    owner: str
    repo: str
    type: str
    token: Optional[str] = None
    localPath: Optional[str] = None
    repoUrl: Optional[str] = None


class WikiSection(BaseModel):
    """
    Model for the wiki sections.
    """

    id: str
    title: str
    pages: List[str]
    subsections: Optional[List[str]] = None


class WikiStructureModel(BaseModel):
    """
    Model for the overall wiki structure.
    """

    id: str
    title: str
    description: str
    pages: List[WikiPage]
    sections: Optional[List[WikiSection]] = None
    rootSections: Optional[List[str]] = None


class WikiCacheData(BaseModel):
    """
    Model for the data to be stored in the wiki cache.
    """

    wiki_structure: WikiStructureModel
    generated_pages: Dict[str, WikiPage]
    repo_url: Optional[str] = None  # compatible for old cache
    repo: Optional[RepoInfo] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    version: Optional[int] = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    repo_snapshot: Optional[RepoSnapshot] = None


class WikiCacheRequest(BaseModel):
    """
    Model for the request body when saving wiki cache.
    """

    repo: RepoInfo
    language: str
    wiki_structure: WikiStructureModel
    generated_pages: Dict[str, WikiPage]
    provider: str
    model: str
    version: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    repo_snapshot: Optional[RepoSnapshot] = None


class WikiExportRequest(BaseModel):
    """
    Model for requesting a wiki export.
    """

    repo_url: str = Field(..., description="URL of the repository")
    pages: List[WikiPage] = Field(..., description="List of wiki pages to export")
    format: Literal["markdown", "json"] = Field(
        ..., description="Export format (markdown or json)"
    )


__all__ = [
    "WikiPage",
    "ProcessedProjectEntry",
    "RepoInfo",
    "WikiSection",
    "WikiStructureModel",
    "WikiCacheData",
    "WikiCacheRequest",
    "WikiExportRequest",
    "RepoSnapshot",
    "RepoSnapshotFile",
]
