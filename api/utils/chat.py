"""Chat completion convenience helpers.

The CLI relies on synchronous streaming responses, so this module provides a thin
wrapper around :func:`api.core.chat.generate_chat_completion_core`.
"""

from collections.abc import Generator

from api.core.chat import generate_chat_completion_core


def generate_chat_completion_streaming(
    repo_url: str,
    messages: list[dict[str, str]],
    provider: str,
    model: str,
    repo_type: str = "github",
    token: str | None = None,
    excluded_dirs: list[str] | None = None,
    excluded_files: list[str] | None = None,
    included_dirs: list[str] | None = None,
    included_files: list[str] | None = None,
    file_path: str | None = None,
) -> Generator[str]:
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
