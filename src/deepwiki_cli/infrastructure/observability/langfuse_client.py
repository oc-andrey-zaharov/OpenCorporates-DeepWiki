"""Langfuse client initialization and utilities for observability.

This module provides Langfuse client initialization and helper functions
for tracing wiki generation operations.
"""

import os
from typing import Any

from deepwiki_cli.infrastructure.config.settings import (
    LANGFUSE_BASE_URL,
    LANGFUSE_ENABLED,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)
from deepwiki_cli.shared.structlog import structlog

logger = structlog.get_logger()

_langfuse_client: Any | None = None


def get_langfuse_client() -> Any | None:
    """Get or initialize the Langfuse client.

    Returns:
        Langfuse client instance if enabled and configured, None otherwise.
    """
    global _langfuse_client

    if not LANGFUSE_ENABLED:
        return None

    if _langfuse_client is not None:
        return _langfuse_client

    try:
        from langfuse import Langfuse

        public_key = LANGFUSE_PUBLIC_KEY or os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = LANGFUSE_SECRET_KEY or os.environ.get("LANGFUSE_SECRET_KEY")
        base_url = LANGFUSE_BASE_URL or os.environ.get("LANGFUSE_BASE_URL")

        if not public_key or not secret_key:
            logger.debug(
                "Langfuse not configured: missing public_key or secret_key",
                operation="langfuse_init",
                status="skipped",
            )
            return None

        client_kwargs: dict[str, Any] = {
            "public_key": public_key,
            "secret_key": secret_key,
        }

        if base_url:
            client_kwargs["base_url"] = base_url

        _langfuse_client = Langfuse(**client_kwargs)
        logger.info(
            "Langfuse client initialized",
            operation="langfuse_init",
            status="success",
            base_url=base_url or "default",
        )
        return _langfuse_client

    except ImportError:
        logger.warning(
            "Langfuse package not available",
            operation="langfuse_init",
            status="warning",
        )
        return None
    except Exception as e:
        logger.warning(
            f"Failed to initialize Langfuse client: {e!s}",
            operation="langfuse_init",
            status="error",
            error=str(e),
        )
        return None


def is_langfuse_enabled() -> bool:
    """Check if Langfuse is enabled and configured.

    Returns:
        True if Langfuse is enabled and configured, False otherwise.
    """
    if not LANGFUSE_ENABLED:
        return False

    client = get_langfuse_client()
    return client is not None


def flush_langfuse() -> None:
    """Flush pending Langfuse events.

    Call this before application shutdown to ensure all events are sent.
    """
    client = get_langfuse_client()
    if client is not None:
        try:
            client.flush()
            logger.debug(
                "Langfuse events flushed",
                operation="langfuse_flush",
                status="success",
            )
        except Exception as e:
            logger.warning(
                f"Failed to flush Langfuse events: {e!s}",
                operation="langfuse_flush",
                status="error",
                error=str(e),
            )
