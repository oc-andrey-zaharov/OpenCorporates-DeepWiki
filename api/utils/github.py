"""
Unified GitHub repository structure wrapper.

This module provides a unified interface for fetching GitHub repository structure
that routes to standalone or server mode based on configuration.
"""

import logging
from typing import Dict, Optional

import requests
from requests.exceptions import ConnectionError, Timeout

from api.cli.config import load_config
from api.config import GITHUB_TOKEN
from api.core.github import get_github_repo_structure_standalone
from api.utils.mode import (
    check_server_health_with_retry,
    get_server_url,
    is_server_mode,
    should_fallback,
)

logger = logging.getLogger(__name__)


def get_github_repo_structure(
    owner: str,
    repo: str,
    repo_url: Optional[str] = None,
    access_token: Optional[str] = None,
) -> Dict[str, str]:
    """
    Unified function to get GitHub repository structure.

    Routes to standalone or server mode based on configuration.
    Returns dict with 'file_tree', 'readme', and 'default_branch' keys.

    Args:
        owner: Repository owner
        repo: Repository name
        repo_url: Optional full repository URL (for GitHub Enterprise)
        access_token: Optional GitHub access token (CLI arg > config > env var)

    Returns:
        Dictionary with file_tree, readme, and default_branch keys

    Raises:
        ConnectionError: If server mode enabled but server unavailable and auto_fallback is False
        Exception: For other errors during processing
    """
    config = load_config()

    # Determine token precedence: CLI arg > config > env var
    token = access_token
    if not token:
        # Could check config for token in the future
        token = GITHUB_TOKEN

    if is_server_mode():
        # Check server health first
        server_url = get_server_url()
        if not check_server_health_with_retry(server_url, timeout=5):
            if should_fallback():
                logger.warning(
                    f"Server unavailable at {server_url}, falling back to standalone mode"
                )
                return get_github_repo_structure_standalone(
                    owner, repo, repo_url, token
                )
            else:
                raise ConnectionError(
                    f"Server mode enabled but server unavailable at {server_url}. "
                    "Set 'auto_fallback: true' in config or start the server."
                )
        else:
            return get_github_repo_structure_via_server(owner, repo, repo_url, token)
    else:
        return get_github_repo_structure_standalone(owner, repo, repo_url, token)


def get_github_repo_structure_via_server(
    owner: str,
    repo: str,
    repo_url: Optional[str] = None,
    access_token: Optional[str] = None,
) -> Dict[str, str]:
    """
    Server mode: HTTP request to FastAPI server.

    Requires server to be running.

    Args:
        owner: Repository owner
        repo: Repository name
        repo_url: Optional full repository URL
        access_token: Optional GitHub access token (not used in server mode, server uses env var)

    Returns:
        Dictionary with file_tree, readme, and default_branch keys

    Raises:
        ConnectionError: If server connection fails
        Exception: For other errors
    """
    config = load_config()
    server_url = get_server_url()

    params = {"owner": owner, "repo": repo}
    if repo_url:
        params["repo_url"] = repo_url

    try:
        response = requests.get(
            f"{server_url}/github/repo/structure",
            params=params,
            timeout=60,
        )

        if not response.ok:
            error_detail = "Unknown error"
            try:
                error_data = response.json()
                error_detail = error_data.get("error", error_detail)
            except (
                ValueError,
                requests.exceptions.JSONDecodeError,
                AttributeError,
            ) as e:
                error_detail = (
                    getattr(response, "text", None)
                    or getattr(response, "reason", None)
                    or str(e)
                )

            raise Exception(f"Server error: {response.status_code} - {error_detail}")

        return response.json()

    except (ConnectionError, Timeout) as e:
        # If server connection fails, try fallback if enabled
        if should_fallback():
            logger.warning(
                f"Server request failed: {e}, falling back to standalone mode"
            )
            return get_github_repo_structure_standalone(
                owner, repo, repo_url, access_token
            )
        else:
            raise
