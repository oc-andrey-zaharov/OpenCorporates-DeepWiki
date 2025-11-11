"""System/status routes for the API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    """Simple health check endpoint for Docker and monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "deepwiki-api",
    }


@router.get("/")
async def root(request: Request):
    """Return a friendly welcome message and list available endpoints."""
    endpoints: dict[str, list[str]] = {}
    for route in request.app.routes:
        if not getattr(route, "methods", None) or not getattr(route, "path", None):
            continue
        if route.path in {"/openapi.json", "/docs", "/redoc", "/favicon.ico"}:
            continue
        path_parts = route.path.strip("/").split("/")
        group = path_parts[0].capitalize() if path_parts[0] else "Root"
        method_list = list(route.methods - {"HEAD", "OPTIONS"})
        for method in method_list:
            endpoints.setdefault(group, []).append(f"{method} {route.path}")

    for group in endpoints:
        endpoints[group].sort()

    return {
        "message": "Welcome to DeepWiki API",
        "version": "1.0.0",
        "endpoints": endpoints,
    }


__all__ = ["router"]
