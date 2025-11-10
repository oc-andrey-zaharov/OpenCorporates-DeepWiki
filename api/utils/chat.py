"""
Unified chat completion wrapper.

This module provides a unified interface for chat completions that routes
to standalone or server mode based on configuration.
"""

import logging
from typing import Dict, Generator, List, Optional

import requests
from requests.exceptions import ConnectionError, Timeout

from api.cli.config import load_config
from api.core.chat import generate_chat_completion_core
from api.utils.mode import (
    check_server_health_with_retry,
    get_server_url,
    is_server_mode,
    should_fallback,
)

logger = logging.getLogger(__name__)


def generate_chat_completion_streaming(
    repo_url: str,
    messages: List[Dict[str, str]],
    provider: str,
    model: str,
    repo_type: str = "github",
    token: Optional[str] = None,
    excluded_dirs: Optional[List[str]] = None,
    excluded_files: Optional[List[str]] = None,
    included_dirs: Optional[List[str]] = None,
    included_files: Optional[List[str]] = None,
    file_path: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Unified streaming chat completion.

    Routes to standalone or server mode based on configuration.
    Yields chunks as they arrive for progress feedback.

    Args:
        repo_url: Repository URL
        messages: List of message dicts with 'role' and 'content' keys
        provider: Model provider
        model: Model name
        repo_type: Repository type (default: "github")
        token: Optional access token for private repositories
        excluded_dirs: Optional list of directories to exclude
        excluded_files: Optional list of file patterns to exclude
        included_dirs: Optional list of directories to include exclusively
        included_files: Optional list of file patterns to include exclusively
        file_path: Optional path to a file in the repository

    Yields:
        str: Text chunks as they arrive

    Raises:
        ConnectionError: If server mode enabled but server unavailable and auto_fallback is False
        Exception: For other errors during processing
    """
    if is_server_mode():
        # Check server health first
        server_url = get_server_url()
        if not check_server_health_with_retry(server_url, timeout=5):
            if should_fallback():
                logger.warning(
                    f"Server unavailable at {server_url}, falling back to standalone mode"
                )
                yield from _generate_standalone(
                    repo_url,
                    messages,
                    provider,
                    model,
                    repo_type,
                    token,
                    excluded_dirs,
                    excluded_files,
                    included_dirs,
                    included_files,
                    file_path,
                )
            else:
                raise ConnectionError(
                    f"Server mode enabled but server unavailable at {server_url}. "
                    "Set 'auto_fallback: true' in config or start the server."
                )
        else:
            yield from _generate_via_server(
                repo_url,
                messages,
                provider,
                model,
                repo_type,
                token,
                excluded_dirs,
                excluded_files,
                included_dirs,
                included_files,
                file_path,
            )
    else:
        yield from _generate_standalone(
            repo_url,
            messages,
            provider,
            model,
            repo_type,
            token,
            excluded_dirs,
            excluded_files,
            included_dirs,
            included_files,
            file_path,
        )


def _generate_standalone(
    repo_url: str,
    messages: List[Dict[str, str]],
    provider: str,
    model: str,
    repo_type: str,
    token: Optional[str],
    excluded_dirs: Optional[List[str]],
    excluded_files: Optional[List[str]],
    included_dirs: Optional[List[str]],
    included_files: Optional[List[str]],
    file_path: Optional[str],
) -> Generator[str, None, None]:
    """
    Standalone mode: direct call to core function.

    Preserves streaming behavior.
    """
    yield from generate_chat_completion_core(
        repo_url=repo_url,
        messages=messages,
        provider=provider,
        model=model,
        repo_type=repo_type,
        token=token,
        excluded_dirs=excluded_dirs,
        excluded_files=excluded_files,
        included_dirs=included_dirs,
        included_files=included_files,
        file_path=file_path,
    )


def _generate_via_server(
    repo_url: str,
    messages: List[Dict[str, str]],
    provider: str,
    model: str,
    repo_type: str,
    token: Optional[str],
    excluded_dirs: Optional[List[str]],
    excluded_files: Optional[List[str]],
    included_dirs: Optional[List[str]],
    included_files: Optional[List[str]],
    file_path: Optional[str],
) -> Generator[str, None, None]:
    """
    Server mode: HTTP request with streaming.

    Yields chunks as received from server.
    """
    config = load_config()
    server_url = get_server_url()
    timeout = config.get("server_timeout", 300)

    # Prepare request body
    request_body = {
        "repo_url": repo_url,
        "messages": messages,
        "provider": provider,
        "model": model,
        "type": repo_type,
    }
    if token:
        request_body["token"] = token
    if file_path:
        request_body["filePath"] = file_path
    if excluded_dirs:
        request_body["excluded_dirs"] = "\n".join(excluded_dirs)
    if excluded_files:
        request_body["excluded_files"] = "\n".join(excluded_files)
    if included_dirs:
        request_body["included_dirs"] = "\n".join(included_dirs)
    if included_files:
        request_body["included_files"] = "\n".join(included_files)

    try:
        response = requests.post(
            f"{server_url}/chat/completions/stream",
            json=request_body,
            stream=True,
            timeout=timeout,
        )

        if not response.ok:
            raise Exception(f"Server error: {response.status_code} - {response.text}")

        # Yield chunks as they arrive
        for line in response.iter_lines(decode_unicode=True):
            if line:
                yield line

    except (ConnectionError, Timeout) as e:
        # If server connection fails, try fallback if enabled
        if should_fallback():
            logger.warning(
                f"Server request failed: {e}, falling back to standalone mode"
            )
            yield from _generate_standalone(
                repo_url,
                messages,
                provider,
                model,
                repo_type,
                token,
                excluded_dirs,
                excluded_files,
                included_dirs,
                included_files,
                file_path,
            )
        else:
            raise
