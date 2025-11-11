"""Routes for exporting generated wiki content."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from api.utils.export import generate_json_export, generate_markdown_export

if TYPE_CHECKING:
    from api.models import WikiExportRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["wiki"])


@router.post("/wiki")
async def export_wiki(request: WikiExportRequest):
    """Export wiki content as Markdown or JSON."""
    try:
        logger.info("Exporting wiki for %s in %s format", request.repo_url, request.format)
        repo_parts = request.repo_url.rstrip("/").split("/")
        repo_name = repo_parts[-1] if repo_parts else "wiki"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if request.format == "markdown":
            content = generate_markdown_export(request.repo_url, request.pages)
            filename = f"{repo_name}_wiki_{timestamp}.md"
            media_type = "text/markdown"
        else:
            content = generate_json_export(request.repo_url, request.pages)
            filename = f"{repo_name}_wiki_{timestamp}.json"
            media_type = "application/json"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as exc:
        logger.exception("Error exporting wiki: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error exporting wiki: {exc}")


__all__ = ["router"]
