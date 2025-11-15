"""Wiki content generation convenience helpers.

The CLI relies on synchronous streaming responses, so this module provides a thin
wrapper around :func:`deepwiki_cli.core.completion.generate_wiki_content`.
"""

from collections.abc import Generator

from deepwiki_cli.core.completion import generate_wiki_content


def generate_wiki_content_streaming(
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
    """Generate wiki content with streaming support."""
    yield from generate_wiki_content(
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
