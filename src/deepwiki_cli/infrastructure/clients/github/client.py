"""GitHub API core functionality.

This module provides synchronous GitHub repository structure fetching
that can be used by both CLI and server.
"""

import base64
import logging
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException

from deepwiki_cli.infrastructure.config.settings import GITHUB_TOKEN

logger = logging.getLogger(__name__)


def get_github_repo_structure_standalone(
    owner: str,
    repo: str,
    repo_url: str | None = None,
    access_token: str | None = None,
) -> dict[str, str]:
    """Get GitHub repository structure (file tree and README) synchronously.

    Args:
        owner: Repository owner
        repo: Repository name
        repo_url: Optional full repository URL (for GitHub Enterprise)
        access_token: Optional GitHub access token (takes precedence over env var)

    Returns:
        Dictionary with keys:
            - file_tree: String representation of file tree
            - readme: README.md content
            - default_branch: Default branch name
            - tree_files: Raw Git tree entries for blobs

    Raises:
        Exception: If repository structure cannot be fetched
    """
    # Determine the GitHub API base URL based on the repository URL
    if repo_url:
        try:
            parsed_url = urlparse(repo_url)
            hostname = parsed_url.hostname

            if hostname == "github.com":
                api_base = "https://api.github.com"
            else:
                # GitHub Enterprise - API is typically at https://domain/api/v3/
                api_base = f"{parsed_url.scheme}://{hostname}/api/v3"
        except Exception:
            api_base = "https://api.github.com"
    else:
        api_base = "https://api.github.com"

    # Prepare headers with token (parameter > env var)
    headers = {"Accept": "application/vnd.github.v3+json"}

    token = access_token or GITHUB_TOKEN
    if token:
        headers["Authorization"] = f"Bearer {token}"
        logger.info("Using GitHub token for repository access")
    else:
        logger.warning(
            "No GitHub token provided. Requests may fail for private repositories.",
        )

    # First, try to get the default branch from the repository info
    default_branch = "main"
    try:
        repo_info_response = requests.get(
            f"{api_base}/repos/{owner}/{repo}",
            headers=headers,
            timeout=30,
        )

        if repo_info_response.ok:
            repo_data = repo_info_response.json()
            default_branch = repo_data.get("default_branch", "main")
            logger.info(f"Found default branch: {default_branch}")
        else:
            logger.warning(
                f"Could not fetch repository info: {repo_info_response.status_code}",
            )
    except Exception as e:
        logger.warning(f"Error fetching repository info: {e}")

    # Try to get the tree data for the default branch and common branch names
    tree_data = None
    branches_to_try = [default_branch, "main", "master"]
    branches_to_try = list(
        dict.fromkeys(branches_to_try),
    )  # Remove duplicates while preserving order

    for branch in branches_to_try:
        try:
            api_url = f"{api_base}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            logger.info(f"Fetching repository structure from branch: {branch}")

            response = requests.get(api_url, headers=headers, timeout=30)

            if response.ok:
                tree_data = response.json()
                logger.info("Successfully fetched repository structure")
                break
            error_data = response.text
            logger.warning(
                f"Error fetching branch {branch}: {response.status_code} - {error_data}",
            )
        except RequestException as e:
            logger.exception(f"Network error fetching branch {branch}: {e}")

    if not tree_data or "tree" not in tree_data:
        error_msg = "Could not fetch repository structure. Repository might not exist, be empty, or private."
        if not token:
            error_msg += " No GitHub token provided. Please provide a token via parameter or GITHUB_TOKEN environment variable."
        raise Exception(error_msg)

    # Convert tree data to a string representation
    blob_entries = [item for item in tree_data["tree"] if item.get("type") == "blob"]
    file_tree_data = "\n".join(item["path"] for item in blob_entries)
    tree_files = [
        {
            "path": item.get("path"),
            "sha": item.get("sha"),
            "size": item.get("size"),
            "type": item.get("type"),
            "mode": item.get("mode"),
        }
        for item in blob_entries
    ]

    # Try to fetch README.md content
    readme_content = ""
    try:
        readme_response = requests.get(
            f"{api_base}/repos/{owner}/{repo}/readme",
            headers=headers,
            timeout=30,
        )

        if readme_response.ok:
            readme_data = readme_response.json()
            readme_content = base64.b64decode(readme_data["content"]).decode("utf-8")
            logger.info("Successfully fetched README.md")
        else:
            logger.warning(
                f"Could not fetch README.md, status: {readme_response.status_code}",
            )
    except Exception as e:
        logger.warning(f"Error fetching README.md: {e}")

    return {
        "file_tree": file_tree_data,
        "readme": readme_content,
        "default_branch": default_branch,
        "tree_files": tree_files,
    }
