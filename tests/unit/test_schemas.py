"""Unit tests for structured schema models."""

from __future__ import annotations

from deepwiki_cli.domain.schemas import (
    PromptMetadata,
    PromptSchemaName,
    RAGContextSchema,
    RAGDocumentSchema,
    WikiPageMetadata,
    WikiPageSchema,
    WikiStructurePageSchema,
    WikiStructureSchema,
)


def test_wiki_structure_schema_round_trip() -> None:
    """Ensure schemas serialize to compact JSON and back."""
    structure = WikiStructureSchema(
        schema_name=PromptSchemaName.WIKI_STRUCTURE,
        title="Example Wiki",
        description="Covers the important modules.",
        pages=[
            WikiStructurePageSchema(
                page_id="overview",
                title="Overview",
                summary="Introductory description.",
                importance="high",
                relevant_files=["README.md"],
                related_page_ids=[],
                diagram_suggestions=["flowchart"],
            ),
        ],
        metadata=PromptMetadata(repo_name="example/repo"),
    )

    compact = structure.to_compact_json()
    assert "\n" not in compact
    parsed = WikiStructureSchema.model_validate_json(compact)
    assert parsed.title == "Example Wiki"
    assert parsed.pages[0].relevant_files == ["README.md"]


def test_prompt_metadata_schema_generation() -> None:
    """json_schema_dict should include metadata description."""
    schema = WikiStructureSchema.model_json_schema()
    assert "properties" in schema
    assert "pages" in schema["properties"]


def test_rag_context_schema_validation() -> None:
    """RAG context should accept markdown documents."""
    context = RAGContextSchema(
        schema_name=PromptSchemaName.RAG_CONTEXT,
        query="What is the pipeline?",
        documents=[
            RAGDocumentSchema(
                document_id="doc-1",
                file_path="src/pipeline.py",
                content="## Pipeline\nDetails...",
                score=0.9,
                metadata={"language": "python"},
            ),
        ],
        conversation_history=[{"role": "user", "content": "Hello"}],
        markdown_instructions="Reply in markdown.",
    )
    payload = context.to_compact_json()
    assert payload.startswith("{")
    parsed = RAGContextSchema.model_validate_json(payload)
    assert parsed.documents[0].file_path == "src/pipeline.py"


def test_wiki_page_schema_validation() -> None:
    """Wiki page schema should round-trip metadata and content."""
    schema = WikiPageSchema(
        page_id="page-1",
        title="Overview",
        importance="high",
        metadata=WikiPageMetadata(
            summary="Brief summary.",
            keywords=["overview"],
            related_page_ids=["page-2"],
            referenced_files=["README.md", "src/app.py"],
            diagram_types=["flowchart"],
        ),
        content="# Overview",
    )
    payload = schema.to_compact_json()
    parsed = WikiPageSchema.model_validate_json(payload)
    assert parsed.metadata.referenced_files == ["README.md", "src/app.py"]
