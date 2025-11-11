"""Core business logic module for DeepWiki.

This module contains the core functionality that can be used by both
the CLI (standalone mode) and the FastAPI server.
"""

from api.core.completion import generate_wiki_content
from api.core.github import get_github_repo_structure_standalone

__all__ = [
    "generate_wiki_content",
    "get_github_repo_structure_standalone",
]
