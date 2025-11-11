"""Routes that expose repository metadata (local and GitHub)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from api.server.services.repository import (
    describe_github_repository,
    describe_local_repository,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["repositories"])


@router.get("/local_repo/structure")
async def get_local_repo_structure(
    path: str = Query(None, description="Path to local repository"),
):
    """Return the file tree and README content for a local repository."""
    try:
        return describe_local_repository(path)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Error processing local repository: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing local repository: {exc}",
        ) from exc


@router.get("/github/repo/structure")
async def get_github_repo_structure(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    repo_url: str | None = Query(None, description="Full repository URL"),
):
    """Return the file tree and README content for a GitHub repository."""
    try:
        return describe_github_repository(owner=owner, repo=repo, repo_url=repo_url)
    except Exception as exc:
        error_msg = str(exc)
        logger.exception("Error fetching GitHub repository structure: %s", error_msg)
        if "Could not fetch repository structure" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg) from exc
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching repository structure: {error_msg}",
        ) from exc


__all__ = ["router"]
