"""Helpers for reusing RAG state across multiple wiki generation steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel

from deepwiki_cli.services.rag import RAG

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass
class WikiGenerationContext:
    """Encapsulates a prepared RAG instance plus its configuration."""

    repo_url: str
    repo_type: str
    provider: str
    model: str
    _rag: RAG = field(repr=False)
    token: str | None = None
    excluded_dirs: list[str] | None = None
    excluded_files: list[str] | None = None
    included_dirs: list[str] | None = None
    included_files: list[str] | None = None

    @classmethod
    def prepare(
        cls,
        repo_url: str,
        repo_type: str,
        provider: str,
        model: str,
        token: str | None = None,
        excluded_dirs: list[str] | None = None,
        excluded_files: list[str] | None = None,
        included_dirs: list[str] | None = None,
        included_files: list[str] | None = None,
        force_rebuild_embeddings: bool = False,
    ) -> WikiGenerationContext:
        """Build and prime a context for repeated completions.

        Args:
            force_rebuild_embeddings: If True, discard any cached embedding database
                and rebuild it before generating content.
        """
        rag = RAG(provider=provider, model=model)
        rag.prepare_retriever(
            repo_url,
            repo_type,
            token,
            excluded_dirs,
            excluded_files,
            included_dirs,
            included_files,
            force_rebuild=force_rebuild_embeddings,
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
        messages: list[dict[str, str]],
        *,
        structured_schema: type[BaseModel] | None = None,
        file_path: str | None = None,
    ) -> Generator[str]:
        """Yield completion chunks using the cached retriever."""
        from deepwiki_cli.application.wiki.generate_content import generate_wiki_content

        return generate_wiki_content(
            repo_url=self.repo_url,
            messages=messages,
            provider=self.provider,
            model=self.model,
            repo_type=self.repo_type,
            structured_schema=structured_schema,
            token=self.token,
            excluded_dirs=self.excluded_dirs,
            excluded_files=self.excluded_files,
            included_dirs=self.included_dirs,
            included_files=self.included_files,
            file_path=file_path,
            prepared_rag=self._rag,
        )


__all__ = ["WikiGenerationContext"]

