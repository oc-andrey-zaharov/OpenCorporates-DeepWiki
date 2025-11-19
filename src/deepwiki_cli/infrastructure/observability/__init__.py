"""Observability module for DeepWiki.

Provides Langfuse integration for tracing and metrics.
"""

from deepwiki_cli.infrastructure.observability.langfuse_client import (
    flush_langfuse,
    get_langfuse_client,
    is_langfuse_enabled,
)

__all__ = [
    "flush_langfuse",
    "get_langfuse_client",
    "is_langfuse_enabled",
]

