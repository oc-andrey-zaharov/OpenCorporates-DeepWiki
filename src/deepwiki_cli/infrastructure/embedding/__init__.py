"""Embedding infrastructure."""

from deepwiki_cli.infrastructure.embedding.embedder import get_embedder
from deepwiki_cli.infrastructure.embedding.ollama_patch import (
    OllamaDocumentProcessor,
    OllamaModelNotFoundError,
    check_ollama_model_exists,
)

__all__ = [
    "OllamaDocumentProcessor",
    "OllamaModelNotFoundError",
    "check_ollama_model_exists",
    "get_embedder",
]


