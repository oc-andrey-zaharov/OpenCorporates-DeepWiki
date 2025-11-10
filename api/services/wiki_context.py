"""
Helpers for reusing RAG state across multiple wiki generation steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator, List, Optional

from api.core.chat import generate_chat_completion_core
from api.services.rag import RAG


@dataclass
class WikiGenerationContext:
    """Encapsulates a prepared RAG instance plus its configuration."""

    repo_url: str
    repo_type: str
    provider: str
    model: str
    _rag: RAG = field(repr=False)
    token: Optional[str] = None
    excluded_dirs: Optional[List[str]] = None
    excluded_files: Optional[List[str]] = None
    included_dirs: Optional[List[str]] = None
    included_files: Optional[List[str]] = None

    @classmethod
    def prepare(
        cls,
        repo_url: str,
        repo_type: str,
        provider: str,
        model: str,
        token: Optional[str] = None,
        excluded_dirs: Optional[List[str]] = None,
        excluded_files: Optional[List[str]] = None,
        included_dirs: Optional[List[str]] = None,
        included_files: Optional[List[str]] = None,
    ) -> "WikiGenerationContext":
        """Build and prime a context for repeated completions."""
        rag = RAG(provider=provider, model=model)
        rag.prepare_retriever(
            repo_url,
            repo_type,
            token,
            excluded_dirs,
            excluded_files,
            included_dirs,
            included_files,
        )
        return cls(
            repo_url=repo_url,
            repo_type=repo_type,
            provider=provider,
            model=model,
            token=token,
            excluded_dirs=list(excluded_dirs) if excluded_dirs else None,
            excluded_files=list(excluded_files) if excluded_files else None,
            included_dirs=list(included_dirs) if included_dirs else None,
            included_files=list(included_files) if included_files else None,
            _rag=rag,
        )

    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        file_path: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Yield completion chunks using the cached retriever."""
        return generate_chat_completion_core(
            repo_url=self.repo_url,
            messages=messages,
            provider=self.provider,
            model=self.model,
            repo_type=self.repo_type,
            token=self.token,
            excluded_dirs=self.excluded_dirs,
            excluded_files=self.excluded_files,
            included_dirs=self.included_dirs,
            included_files=self.included_files,
            file_path=file_path,
            prepared_rag=self._rag,
        )


__all__ = ["WikiGenerationContext"]
