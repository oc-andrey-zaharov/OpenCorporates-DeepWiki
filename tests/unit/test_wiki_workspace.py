"""Tests for editable wiki workspaces."""

from __future__ import annotations

import json
from pathlib import Path

from deepwiki_cli.models import WikiPage, WikiSection, WikiStructureModel
from deepwiki_cli.utils.wiki_workspace import (
    ExportManifest,
    export_markdown_workspace,
    slugify,
    sync_manifest,
)


def _build_pages() -> list[WikiPage]:
    page_one = WikiPage(
        id="overview",
        title="Project Overview",
        content="Original overview content.",
        filePaths=["README.md"],
        importance="high",
        relatedPages=["setup"],
    )
    page_two = WikiPage(
        id="setup",
        title="Getting Started",
        content="Install dependencies.",
        filePaths=["setup.md"],
        importance="medium",
        relatedPages=[],
    )
    return [page_one, page_two]


def _build_structure(pages: list[WikiPage]) -> WikiStructureModel:
    section = WikiSection(id="intro", title="Introduction", pages=[page.id for page in pages])
    return WikiStructureModel(
        id="root",
        title="Demo",
        description="Demo wiki",
        pages=pages,
        sections=[section],
        rootSections=[section.id],
    )


def test_export_and_sync_multi_layout(tmp_path):
    cache_file = tmp_path / "cache.json"
    pages = _build_pages()
    structure = _build_structure(pages)
    cache_payload = {
        "repo": {"owner": "acme", "repo": "demo", "repoUrl": "https://github.com/acme/demo"},
        "wiki_structure": json.loads(structure.model_dump_json()),
        "generated_pages": {page.id: json.loads(page.model_dump_json()) for page in pages},
    }
    cache_file.write_text(json.dumps(cache_payload), encoding="utf-8")

    manifest = ExportManifest(
        owner="acme",
        repo="demo",
        repo_type="github",
        version=1,
        cache_file=str(cache_file),
        layout="multi",
        format="markdown",
        root_dir=str(tmp_path / "workspace"),
        artifact=str(tmp_path / "workspace"),
        repo_url="https://github.com/acme/demo",
    )

    manifest = export_markdown_workspace(pages=pages, structure=structure, manifest=manifest)
    first_page = manifest.pages[0]
    exported_file = Path(manifest.root_dir) / first_page.relative_path

    original_text = exported_file.read_text(encoding="utf-8")
    updated_text = original_text.replace(
        "Original overview content.",
        "Updated overview content with more detail.",
    ).replace(
        "# Project Overview",
        "# Project Overview v2",
    )
    exported_file.write_text(updated_text, encoding="utf-8")

    summary = sync_manifest(manifest, changed_paths={exported_file})
    assert summary["updated"] == 1

    updated_cache = json.loads(cache_file.read_text(encoding="utf-8"))
    assert updated_cache["generated_pages"]["overview"]["content"] == "Updated overview content with more detail."
    assert updated_cache["generated_pages"]["overview"]["title"] == "Project Overview v2"


def test_slugify_outputs_safe_names():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("***") == "page"
