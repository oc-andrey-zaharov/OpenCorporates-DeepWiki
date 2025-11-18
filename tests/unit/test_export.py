#!/usr/bin/env python3
"""Unit tests for api/utils/export.py.

Tests export functions for generating markdown and JSON exports.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add the parent directory to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from deepwiki_cli.application.export.export import (
    generate_json_export,
    generate_markdown_export,
)
from deepwiki_cli.domain.models import WikiPage


@pytest.mark.unit
class TestGenerateMarkdownExport:
    """Tests for generate_markdown_export function."""

    def test_generate_markdown_export_single_page(self) -> None:
        """Test generating markdown export with single page."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content of page 1",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=[],
                metadata={"summary": "Overview", "keywords": ["core"]},
            ),
        ]

        result = generate_markdown_export(repo_url, pages)

        assert "# Wiki Documentation for" in result
        assert repo_url in result
        assert "## Page 1" in result
        assert "Content of page 1" in result
        assert "Table of Contents" in result
        assert "### Metadata" in result
        assert "Overview" in result

    def test_generate_markdown_export_multiple_pages(self) -> None:
        """Test generating markdown export with multiple pages."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content 1",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=["page2"],
            ),
            WikiPage(
                id="page2",
                title="Page 2",
                content="Content 2",
                filePaths=["file2.py"],
                importance="medium",
                relatedPages=["page1"],
            ),
        ]

        result = generate_markdown_export(repo_url, pages)

        assert "## Page 1" in result
        assert "## Page 2" in result
        assert "Content 1" in result
        assert "Content 2" in result
        assert "Related Pages" in result
        assert "[Page 2](#page2)" in result

    def test_generate_markdown_export_with_related_pages(self) -> None:
        """Test markdown export includes related pages links."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content 1",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=["page2", "page3"],
            ),
            WikiPage(
                id="page2",
                title="Page 2",
                content="Content 2",
                filePaths=["file2.py"],
                importance="medium",
                relatedPages=[],
            ),
            WikiPage(
                id="page3",
                title="Page 3",
                content="Content 3",
                filePaths=["file3.py"],
                importance="low",
                relatedPages=[],
            ),
        ]

        result = generate_markdown_export(repo_url, pages)

        # Check that related pages are linked
        assert "[Page 2](#page2)" in result
        assert "[Page 3](#page3)" in result
        assert "Related topics:" in result

    def test_generate_markdown_export_empty_pages(self) -> None:
        """Test generating markdown export with empty pages list."""
        repo_url = "https://github.com/owner/repo"
        pages = []

        result = generate_markdown_export(repo_url, pages)

        assert "# Wiki Documentation for" in result
        assert repo_url in result
        assert "Table of Contents" in result
        assert "##" not in result.split("Table of Contents")[1]  # No pages after TOC

    def test_generate_markdown_export_includes_timestamp(self) -> None:
        """Test that markdown export includes generation timestamp."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=[],
            ),
        ]

        result = generate_markdown_export(repo_url, pages)

        assert "Generated on:" in result
        # Check for date format YYYY-MM-DD
        assert "20" in result  # Year should be present

    def test_generate_markdown_export_page_anchors(self) -> None:
        """Test that markdown export includes page anchors."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=[],
            ),
        ]

        result = generate_markdown_export(repo_url, pages)

        assert "<a id='page1'></a>" in result
        assert "[Page 1](#page1)" in result  # TOC link


@pytest.mark.unit
class TestGenerateJsonExport:
    """Tests for generate_json_export function."""

    def test_generate_json_export_single_page(self) -> None:
        """Test generating JSON export with single page."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content 1",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=[],
                metadata={"summary": "Intro"},
            ),
        ]

        result = generate_json_export(repo_url, pages)
        data = json.loads(result)

        assert "metadata" in data
        assert "pages" in data
        assert data["metadata"]["repository"] == repo_url
        assert data["metadata"]["page_count"] == 1
        assert len(data["pages"]) == 1
        assert data["pages"][0]["id"] == "page1"
        assert data["pages"][0]["title"] == "Page 1"
        assert data["pages"][0]["metadata"]["summary"] == "Intro"

    def test_generate_json_export_multiple_pages(self) -> None:
        """Test generating JSON export with multiple pages."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content 1",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=[],
            ),
            WikiPage(
                id="page2",
                title="Page 2",
                content="Content 2",
                filePaths=["file2.py"],
                importance="medium",
                relatedPages=["page1"],
            ),
        ]

        result = generate_json_export(repo_url, pages)
        data = json.loads(result)

        expected_page_count = 2
        assert data["metadata"]["page_count"] == expected_page_count
        assert len(data["pages"]) == expected_page_count
        assert data["pages"][0]["id"] == "page1"
        assert data["pages"][1]["id"] == "page2"

    def test_generate_json_export_empty_pages(self) -> None:
        """Test generating JSON export with empty pages list."""
        repo_url = "https://github.com/owner/repo"
        pages = []

        result = generate_json_export(repo_url, pages)
        data = json.loads(result)

        assert data["metadata"]["repository"] == repo_url
        assert data["metadata"]["page_count"] == 0
        assert len(data["pages"]) == 0

    def test_generate_json_export_includes_timestamp(self) -> None:
        """Test that JSON export includes generation timestamp."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=[],
            ),
        ]

        result = generate_json_export(repo_url, pages)
        data = json.loads(result)

        assert "generated_at" in data["metadata"]
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(data["metadata"]["generated_at"])

    def test_generate_json_export_pretty_formatting(self) -> None:
        """Test that JSON export is pretty formatted."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content",
                filePaths=["file1.py"],
                importance="high",
                relatedPages=[],
            ),
        ]

        result = generate_json_export(repo_url, pages)

        # Pretty JSON should have newlines
        assert "\n" in result
        # Should be valid JSON
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_generate_json_export_preserves_page_data(self) -> None:
        """Test that JSON export preserves all page data."""
        repo_url = "https://github.com/owner/repo"
        pages = [
            WikiPage(
                id="page1",
                title="Page 1",
                content="Content with special chars: <>&\"'",
                filePaths=["file1.py", "file2.py"],
                importance="high",
                relatedPages=["page2", "page3"],
            ),
        ]

        result = generate_json_export(repo_url, pages)
        data = json.loads(result)

        page_data = data["pages"][0]
        assert page_data["id"] == "page1"
        assert page_data["title"] == "Page 1"
        assert page_data["content"] == "Content with special chars: <>&\"'"
        assert page_data["filePaths"] == ["file1.py", "file2.py"]
        assert page_data["importance"] == "high"
        assert page_data["relatedPages"] == ["page2", "page3"]
