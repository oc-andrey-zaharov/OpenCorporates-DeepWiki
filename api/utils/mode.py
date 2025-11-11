"""Mode detection and server health checking utilities.

This module provides functions to detect whether to use server mode
or standalone mode, and to check server health.
"""

import logging
import time

import requests
from requests.exceptions import RequestException, Timeout

from api.cli.config import load_config

logger = logging.getLogger(__name__)


def is_server_mode() -> bool:
    """Check if server mode is enabled in configuration.

    Returns:
        True if server mode is enabled, False otherwise
    """
    config = load_config()
    return config.get("use_server", False)


def get_server_url() -> str:
    """Get the configured server URL.

    Returns:
        Server URL string
    """
    config = load_config()
    return config.get("server_url", "http://localhost:8001")


def should_fallback() -> bool:
    """Check if auto-fallback is enabled in configuration.

    Returns:
        True if auto-fallback is enabled, False otherwise
    """
    config = load_config()
    return config.get("auto_fallback", True)


def check_server_health(server_url: str | None = None, timeout: int = 5) -> bool:
    """Check if the server is available and healthy.

    Args:
        server_url: Optional server URL (defaults to configured URL)
        timeout: Request timeout in seconds

    Returns:
        True if server is healthy, False otherwise
    """
    if server_url is None:
        server_url = get_server_url()

    try:
        response = requests.get(f"{server_url}/", timeout=timeout)
        return response.status_code == 200
    except (RequestException, Timeout) as e:
        logger.debug(f"Server health check failed: {e}")
        return False


def check_server_health_with_retry(
    server_url: str | None = None,
    timeout: int = 5,
    max_retries: int = 3,
    initial_backoff: float = 0.5,
) -> bool:
    """Check server health with exponential backoff retry logic.

    Args:
        server_url: Optional server URL (defaults to configured URL)
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff delay in seconds

    Returns:
        True if server is healthy after retries, False otherwise
    """
    if server_url is None:
        server_url = get_server_url()

    backoff = initial_backoff
    for attempt in range(max_retries):
        if check_server_health(server_url, timeout):
            return True

        if attempt < max_retries - 1:
            logger.debug(
                f"Server health check failed (attempt {attempt + 1}/{max_retries}), "
                f"retrying in {backoff}s...",
            )
            time.sleep(backoff)
            backoff *= 2  # Exponential backoff

    return False
