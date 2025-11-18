"""Embedding infrastructure."""

from deepwiki_cli.infrastructure.embedding.embedder import get_embedder
from deepwiki_cli.infrastructure.embedding.lmstudio_patch import (
    LMStudioDocumentProcessor,
    LMStudioModelNotFoundError,
    check_lmstudio_model_exists,
)

__all__ = [
    "LMStudioDocumentProcessor",
    "LMStudioModelNotFoundError",
    "check_lmstudio_model_exists",
    "get_embedder",
]
