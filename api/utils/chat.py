"""
Chat completion convenience helpers.

The CLI relies on synchronous streaming responses, so this module provides a thin
wrapper around :func:`api.core.chat.generate_chat_completion_core`.
"""

from typing import Dict, Generator, List, Optional

from api.core.chat import generate_chat_completion_core


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
    """Yield completion chunks for the given prompt."""
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
