"""FastAPI application entrypoint wiring together all routers."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.logging_config import setup_logging
from api.server.routes.export import router as export_router
from api.server.routes.models import router as models_router
from api.server.routes.repositories import router as repositories_router
from api.server.routes.system import router as system_router
from api.server.routes.wiki_cache import router as wiki_cache_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DeepWiki API",
    description="API for DeepWiki CLI helpers and cache management",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(models_router)
app.include_router(export_router)
app.include_router(repositories_router)
app.include_router(wiki_cache_router)


__all__ = ["app"]
