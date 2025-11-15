"""Tests for the Ollama document processor integration."""

from __future__ import annotations

import importlib

from adalflow.utils.registry import EntityMapping


def test_ollama_document_processor_registered() -> None:
    """Ensure pickled LocalDB objects can resolve the processor class."""
    module = importlib.import_module(
        "deepwiki_cli.infrastructure.embedding.ollama_patch",
    )
    assert (
        EntityMapping.get("OllamaDocumentProcessor") is module.OllamaDocumentProcessor
    )
