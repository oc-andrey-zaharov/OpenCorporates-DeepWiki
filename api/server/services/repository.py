"""Repository inspection helpers used by FastAPI routes."""

from __future__ import annotations

import logging
import os

from api.config import GITHUB_TOKEN
from api.core.github import get_github_repo_structure_standalone

logger = logging.getLogger(__name__)


def describe_local_repository(path: str) -> dict[str, str]:
    """Return a file tree and README contents for ``path``."""
    if not path:
        raise ValueError("Repository path is required")

    if not os.path.isdir(path):
        raise FileNotFoundError(f"Directory not found: {path}")

    logger.info("Processing local repository at %s", path)
    file_tree_lines = []
    readme_content = ""

    for root, dirs, files in os.walk(path):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d not in {"__pycache__", "node_modules", ".venv"}
        ]
        for file in files:
            if file.startswith(".") or file in {"__init__.py", ".DS_Store"}:
                continue
            rel_dir = os.path.relpath(root, path)
            rel_file = os.path.join(rel_dir, file) if rel_dir != "." else file
            file_tree_lines.append(rel_file)
            if file.lower() == "readme.md" and not readme_content:
                try:
                    with open(os.path.join(root, file), encoding="utf-8") as handle:
                        readme_content = handle.read()
                except Exception as exc:
                    logger.warning("Could not read README.md: %s", exc)
                    readme_content = ""

    file_tree_str = "\n".join(sorted(file_tree_lines))
    return {"file_tree": file_tree_str, "readme": readme_content}


def describe_github_repository(
    owner: str,
    repo: str,
    repo_url: str | None = None,
    token: str | None = None,
) -> dict[str, str]:
    """Fetch repository structure using the GitHub API."""
    try:
        return get_github_repo_structure_standalone(
            owner=owner,
            repo=repo,
            repo_url=repo_url,
            access_token=token or GITHUB_TOKEN,
        )
    except Exception as exc:
        logger.exception("Error fetching GitHub repo structure: %s", exc)
        raise


__all__ = ["describe_github_repository", "describe_local_repository"]
