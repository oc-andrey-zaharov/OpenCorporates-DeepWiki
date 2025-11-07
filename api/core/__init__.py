"""
Core business logic module for DeepWiki.

This module contains the core functionality that can be used by both
the CLI (standalone mode) and the FastAPI server.
"""

from api.core.chat import generate_chat_completion_core
from api.core.github import get_github_repo_structure_standalone

__all__ = [
    "generate_chat_completion_core",
    "get_github_repo_structure_standalone",
]
