"""Routes for interacting with cached wiki artifacts."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.models import ProcessedProjectEntry, WikiCacheData, WikiCacheRequest
from api.server.services import wiki_cache as wiki_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["wiki_cache"])


@router.get("/wiki_cache", response_model=Optional[WikiCacheData])
async def get_cached_wiki(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    repo_type: str = Query(..., description="Repository type (e.g., github)"),
    language: str = Query(
        "en",
        description="Language of the wiki content (always English)",
    ),
    version: int | None = Query(
        None,
        description="Optional cache version (defaults to latest)",
    ),
):
    """Retrieve cached wiki data for a repository."""
    cache_version = version or 1
    language = "en"
    logger.info("Retrieving wiki cache for %s/%s (%s)", owner, repo, repo_type)
    return await wiki_cache_service.read_wiki_cache(
        owner,
        repo,
        repo_type,
        language,
        version=cache_version,
    )


@router.post("/wiki_cache")
async def store_wiki_cache(request_data: WikiCacheRequest):
    """Persist generated wiki data to the server-side cache."""
    request_data.language = "en"
    logger.info(
        "Saving wiki cache for %s/%s (%s)",
        request_data.repo.owner,
        request_data.repo.repo,
        request_data.repo.type,
    )
    success = await wiki_cache_service.save_wiki_cache(request_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save wiki cache")
    return {"message": "Wiki cache saved successfully"}


@router.delete("/wiki_cache")
async def delete_wiki_cache(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    repo_type: str = Query(..., description="Repository type (e.g., github)"),
    language: str = Query(
        "en", description="Language of the wiki content (always English)",
    ),
    version: int | None = Query(
        None,
        description="Optional cache version (defaults to 1)",
    ),
):
    """Delete cached wiki content for the given repository."""
    language = "en"
    requested_version = version or 1
    logger.info("Deleting wiki cache for %s/%s (%s)", owner, repo, repo_type)
    deleted = await wiki_cache_service.delete_wiki_cache(
        owner,
        repo,
        repo_type,
        language,
        requested_version,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Wiki cache not found")
    return {"message": f"Wiki cache for {owner}/{repo} deleted successfully"}


@router.get("/processed_projects", response_model=list[ProcessedProjectEntry])
async def get_processed_projects():
    """List processed projects discovered in the wiki cache directory."""
    try:
        return await wiki_cache_service.list_processed_projects()
    except Exception as exc:
        logger.error("Error listing processed projects: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to list processed projects from server cache.",
        ) from exc


__all__ = ["router"]
