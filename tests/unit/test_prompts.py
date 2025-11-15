"""Unit tests for prompt helpers."""

from __future__ import annotations

from deepwiki_cli.infrastructure.prompts.builders import (
    build_wiki_page_prompt,
    build_wiki_structure_prompt,
)


def test_build_wiki_page_prompt_includes_page_title_and_files() -> None:
    """Test that wiki page prompt includes page title and files."""
    prompt = build_wiki_page_prompt("System Overview", "- [src/app.py]")
    assert "# System Overview" in prompt
    assert "- [src/app.py]" in prompt
    assert "Mermaid" in prompt  # sanity check that template loaded correctly


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
    assert "<file_tree>\nsrc/app.py\n</file_tree>" in prompt
    assert "Create a structured wiki" in prompt
    assert "4-6 pages" in prompt
