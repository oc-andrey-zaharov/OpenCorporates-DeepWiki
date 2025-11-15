"""GitHub repository structure helpers."""

from deepwiki_cli.config import GITHUB_TOKEN
from deepwiki_cli.core.github import get_github_repo_structure_standalone


def get_github_repo_structure(
    owner: str,
    repo: str,
    repo_url: str | None = None,
    access_token: str | None = None,
) -> dict[str, str]:
    """Fetch file tree and README for a repository using direct GitHub API calls."""
    token = access_token or GITHUB_TOKEN
    return get_github_repo_structure_standalone(owner, repo, repo_url, token)
