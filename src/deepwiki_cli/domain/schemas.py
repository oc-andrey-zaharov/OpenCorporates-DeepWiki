"""Structured schema definitions for LLM input/output contracts.

The schemas defined here are intentionally separate from the runtime wiki models
to keep LLM-facing payloads stable and serializable regardless of downstream
storage concerns. Each schema extends :class:`PromptDataSchema`, which provides
helpers for JSON-compact serialization that can be fed directly into model
clients supporting JSON mode or function/tool calling semantics.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from deepwiki_cli.domain.types import WikiImportance


class PromptSchemaName(str, Enum):
    """Canonical identifiers for schemas exchanged with LLMs."""

    FILE_TREE = "file_tree"
    PROMPT = "prompt"
    RAG_CONTEXT = "rag_context"
    WIKI_PAGE = "wiki_page"
    WIKI_STRUCTURE = "wiki_structure"


class PromptMetadata(BaseModel):
    """Optional metadata shared across prompt payloads."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"compact": True})

    correlation_id: str | None = Field(
        default=None,
        description="Correlation identifier propagated through the request pipeline.",
    )
    locale: str = Field(
        default="en",
        description="Language tag for downstream formatting. Defaults to English.",
    )
    repo_name: str | None = Field(
        default=None,
        description="Repository display name when available.",
    )
    repo_url: str | None = Field(
        default=None,
        description="Repository URL for reference. Optional for local runs.",
    )


class PromptDataSchema(BaseModel):
    """Base schema for all structured prompt payloads."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        json_schema_extra={
            "compact": True,
            "notes": (
                "All derived schemas serialize using separators=(',', ':') so the "
                "payload can be streamed directly to JSON-mode capable models."
            ),
        },
    )

    schema_name: PromptSchemaName = Field(
        default=PromptSchemaName.PROMPT,
        description="Declarative schema identifier used by format converters.",
    )
    schema_version: str = Field(
        default="1.0",
        description="Semantic version for tooling compatibility.",
    )
    metadata: PromptMetadata | None = Field(
        default=None,
        description="Request metadata injected by the calling service.",
    )

    def to_compact_json(self) -> str:
        """Serialize the payload in compact JSON form suitable for token-limited IO."""
        return self.model_dump_json(by_alias=True, exclude_none=True, indent=None)

    @classmethod
    def json_schema_dict(cls) -> dict[str, Any]:
        """Expose the JSON schema used by providers that require schema registration."""
        return cls.model_json_schema()


class FileTreeNodeSchema(BaseModel):
    """Node within a structured file tree."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        ...,
        description="Path relative to repository root (use forward slashes).",
    )
    type: Literal["file", "directory"] = Field(
        ...,
        description="Node type to assist visualizers.",
    )
    size: int | None = Field(
        default=None,
        ge=0,
        description="Size in bytes where available for files.",
    )
    children: list["FileTreeNodeSchema"] | None = Field(
        default=None,
        description="Child nodes for directories.",
    )


class FileTreeSchema(PromptDataSchema):
    """Compact representation of a repository tree."""

    schema_name: PromptSchemaName = Field(
        default=PromptSchemaName.FILE_TREE,
        description="Schema identifier used by converters and prompts.",
    )
    root_path: str = Field(
        default="/",
        description="Root prefix used for building relative paths.",
    )
    entries: list[FileTreeNodeSchema] = Field(
        default_factory=list,
        description="Tree entries serialized breadth- or depth-first.",
    )


class WikiStructurePageSchema(BaseModel):
    """Structured representation of a wiki page placeholder."""

    model_config = ConfigDict(extra="forbid")

    page_id: str = Field(..., description="Stable identifier referenced by pages.")
    title: str = Field(..., description="Human readable title for the wiki page.")
    summary: str = Field(
        ...,
        description="1-2 sentence description of what the page covers.",
    )
    importance: WikiImportance = Field(
        ...,
        description="Relative importance determining prioritization.",
    )
    relevant_files: list[str] = Field(
        default_factory=list,
        description="Repository files that should be used for the page content.",
    )
    related_page_ids: list[str] = Field(
        default_factory=list,
        description="Related page identifiers for cross-linking.",
    )
    diagram_suggestions: list[str] = Field(
        default_factory=list,
        description="Optional diagram suggestions (flowchart, sequence, etc.).",
    )


class WikiStructureSchema(PromptDataSchema):
    """Schema returned by structure generation prompts."""

    schema_name: PromptSchemaName = Field(
        default=PromptSchemaName.WIKI_STRUCTURE,
        description="Identifier for wiki structure payloads.",
    )
    title: str = Field(
        ...,
        description="Overall wiki title presented to the user.",
    )
    description: str = Field(
        ...,
        description="High-level overview summarizing repository scope.",
    )
    pages: list[WikiStructurePageSchema] = Field(
        ...,
        min_length=1,
        description="Ordered collection of wiki pages to generate.",
    )


class WikiPageMetadata(BaseModel):
    """Metadata attached to generated wiki pages."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        ...,
        description="Concise summary for navigation UIs.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Search keywords extracted from the page.",
    )
    related_page_ids: list[str] = Field(
        default_factory=list,
        description="Pages that should be cross-linked.",
    )
    referenced_files: list[str] = Field(
        default_factory=list,
        description="Source files cited inside the page.",
    )
    diagram_types: list[str] = Field(
        default_factory=list,
        description="Mermaid diagram types rendered within the page.",
    )


class WikiPageSchema(PromptDataSchema):
    """Schema used for wiki page generation responses."""

    schema_name: PromptSchemaName = Field(
        default=PromptSchemaName.WIKI_PAGE,
        description="Identifier for wiki page payloads.",
    )
    page_id: str = Field(..., description="Identifier matching the structure.")
    title: str = Field(..., description="Wiki page title.")
    importance: WikiImportance = Field(
        ...,
        description="Importance inherited from the structure output.",
    )
    metadata: WikiPageMetadata = Field(
        ...,
        description="Structured metadata for UI and linking.",
    )
    content: str = Field(
        ...,
        description="Markdown content that is rendered to the end user.",
    )


class RAGDocumentSchema(BaseModel):
    """RAG document wrapper containing markdown content."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., description="Stable identifier for the snippet.")
    file_path: str = Field(..., description="Repository path for provenance.")
    content: str = Field(
        ...,
        description="Markdown-formatted content presented to the model.",
    )
    score: float | None = Field(
        default=None,
        description="Optional similarity score for ranking insights.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata persisted for analytics.",
    )


class RAGContextSchema(PromptDataSchema):
    """Schema capturing the context payload for RAG style prompts."""

    schema_name: PromptSchemaName = Field(
        default=PromptSchemaName.RAG_CONTEXT,
        description="Identifier for RAG payloads.",
    )
    query: str = Field(..., description="Normalized user query.")
    documents: list[RAGDocumentSchema] = Field(
        default_factory=list,
        description="Ordered documents shown to the model.",
    )
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Previous user/assistant exchanges in chronological order.",
    )
    markdown_instructions: str = Field(
        ...,
        description="System instructions reinforcing markdown constraints.",
    )
    answer_guidance: str | None = Field(
        default=None,
        description="Optional guidance or rubric to follow.",
    )


__all__ = [
    "FileTreeNodeSchema",
    "FileTreeSchema",
    "PromptDataSchema",
    "PromptMetadata",
    "PromptSchemaName",
    "RAGContextSchema",
    "RAGDocumentSchema",
    "WikiPageMetadata",
    "WikiPageSchema",
    "WikiStructurePageSchema",
    "WikiStructureSchema",
]
