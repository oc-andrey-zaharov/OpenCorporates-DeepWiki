"""Unit tests for prompt helpers."""

from __future__ import annotations

from deepwiki_cli.infrastructure.prompts.builders import (
    RAG_TEMPLATE,
    build_wiki_page_prompt,
    build_wiki_structure_prompt,
)


def test_build_wiki_page_prompt_includes_json_schema() -> None:
    """Test that wiki page prompt embeds schema guidance and inputs."""
    prompt = build_wiki_page_prompt(
        "System Overview",
        "- [src/app.py]",
        page_id="page-1",
        importance="high",
        related_pages=["architecture"],
    )
    assert '"schema_name": "wiki_page"' in prompt
    assert "System Overview" in prompt
    assert "- [src/app.py]" in prompt


def test_build_wiki_structure_prompt_handles_comprehensive_mode() -> None:
    """Test that wiki structure prompt handles comprehensive mode."""
    prompt = build_wiki_structure_prompt(
        file_tree="src/app.py",
        readme="README",
        is_comprehensive=True,
        min_pages=4,
        max_pages=6,
        target_pages=5,
        file_count=42,
    )
    assert "DeepWiki structure planner" in prompt
    assert "```text" in prompt and "src/app.py" in prompt
    assert "comprehensive wiki with 4-6 total pages" in prompt
    assert '"schema_name": "wiki_structure"' in prompt


def test_rag_template_references_context_json() -> None:
    """Ensure the RAG template references the structured context payload."""
    assert "{{ context_json }}" in RAG_TEMPLATE
