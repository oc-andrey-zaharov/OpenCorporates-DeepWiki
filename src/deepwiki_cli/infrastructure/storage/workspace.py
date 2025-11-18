"""Editable wiki workspace helpers."""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import structlog
from watchfiles import watch

if TYPE_CHECKING:
    from collections.abc import Iterable

    from deepwiki_cli.domain.models import WikiPage, WikiStructureModel

logger = structlog.get_logger(__name__)

MANIFEST_FILENAME = ".deepwiki-manifest.json"
RELATED_START = "<!-- deepwiki-related:start -->"
RELATED_END = "<!-- deepwiki-related:end -->"
PAGE_MARKER_PATTERN = re.compile(
    r"<!--\s*deepwiki-page:(?P<payload>[A-Za-z0-9+/=]+)\s*-->",
)
RELATED_BLOCK_PATTERN = re.compile(
    rf"{re.escape(RELATED_START)}.*?{re.escape(RELATED_END)}",
    re.DOTALL,
)


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()


def slugify(value: str) -> str:
    """Convert an arbitrary label into a filesystem-friendly slug."""
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower())
    normalized = normalized.strip("-")
    return normalized or "page"


@dataclass(slots=True)
class ExportedPage:
    """Metadata describing an exported page file."""

    id: str
    title: str
    relative_path: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "title": self.title,
            "relative_path": self.relative_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExportedPage:
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            relative_path=data.get("relative_path"),
        )

    def resolved_path(self, root_dir: Path) -> Path | None:
        if self.relative_path is None:
            return None
        return root_dir / self.relative_path


@dataclass(slots=True)
class ExportManifest:
    """Metadata persisted with editable exports."""

    owner: str | None
    repo: str
    repo_type: str
    version: int
    cache_file: str
    layout: Literal["single", "multi"]
    format: Literal["markdown", "json"]
    root_dir: str
    artifact: str
    repo_url: str | None = None
    language: str = "en"
    pages: list[ExportedPage] = field(default_factory=list)
    created_at: str = field(default_factory=_timestamp)
    last_synced: str | None = None

    @property
    def repo_display(self) -> str:
        if self.owner and self.owner != "local":
            return f"{self.owner}/{self.repo}"
        return self.repo

    @property
    def root_path(self) -> Path:
        return Path(self.root_dir)

    @property
    def artifact_path(self) -> Path:
        return Path(self.artifact)

    @property
    def manifest_path(self) -> Path:
        return self.root_path / MANIFEST_FILENAME

    def watch_targets(self) -> list[Path]:
        if self.layout == "single":
            return [self.artifact_path]
        return [self.root_path]

    def to_dict(self) -> dict:
        return {
            "owner": self.owner,
            "repo": self.repo,
            "repo_type": self.repo_type,
            "version": self.version,
            "cache_file": self.cache_file,
            "layout": self.layout,
            "format": self.format,
            "root_dir": self.root_dir,
            "artifact": self.artifact,
            "repo_url": self.repo_url,
            "language": self.language,
            "pages": [page.to_dict() for page in self.pages],
            "created_at": self.created_at,
            "last_synced": self.last_synced,
        }

    def save(self) -> None:
        """Persist manifest metadata alongside the workspace."""
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )

    @classmethod
    def from_path(cls, manifest_file: Path) -> ExportManifest:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        pages = [ExportedPage.from_dict(entry) for entry in data.get("pages", [])]
        return cls(
            owner=data.get("owner"),
            repo=data["repo"],
            repo_type=data["repo_type"],
            version=data["version"],
            cache_file=data["cache_file"],
            layout=data["layout"],
            format=data["format"],
            root_dir=data["root_dir"],
            artifact=data["artifact"],
            repo_url=data.get("repo_url"),
            language=data.get("language", "en"),
            pages=pages,
            created_at=data.get("created_at", _timestamp()),
            last_synced=data.get("last_synced"),
        )


def workspace_name(owner: str | None, repo: str, version: int) -> str:
    """Build a deterministic workspace directory name."""
    prefix = repo if not owner or owner == "local" else f"{owner}-{repo}"
    return f"{slugify(prefix)}-v{version}"


def encode_marker(page_id: str, title: str) -> str:
    """Encode a metadata marker for page boundaries."""
    payload = json.dumps({"page_id": page_id, "title": title}).encode("utf-8")
    encoded = base64.b64encode(payload).decode("ascii")
    return f"<!-- deepwiki-page:{encoded} -->"


def decode_marker(marker_text: str) -> dict[str, str]:
    """Decode metadata from an embedded marker."""
    payload = base64.b64decode(marker_text.encode("ascii"))
    return json.loads(payload)  # type: ignore[no-any-return]


def _strip_generated_blocks(text: str) -> str:
    """Remove auto-generated related blocks and anchor tags from content."""
    cleaned = RELATED_BLOCK_PATTERN.sub("", text)
    cleaned_lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped.startswith("<a ") and "id=" in stripped:
            # Skip anchor lines that were injected for linking
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _split_title(body: str, default: str) -> tuple[str, str]:
    lines = body.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            new_title = stripped.lstrip("#").strip() or default
            remainder = "\n".join(lines[idx + 1 :]).strip()
            return new_title, remainder
    return default, body.strip()


def _build_section_paths(structure: WikiStructureModel) -> dict[str, list[str]]:
    if not structure or not structure.sections:
        return {}

    section_lookup = {section.id: section for section in structure.sections}
    mapping: dict[str, list[str]] = {}

    def walk(section_id: str, ancestors: list[str]) -> None:
        section = section_lookup.get(section_id)
        if not section:
            return
        path = [*ancestors, section.title]
        for page_id in section.pages:
            mapping[page_id] = path
        for child in section.subsections or []:
            walk(child, path)

    roots = structure.rootSections or [section.id for section in structure.sections]
    for root_id in roots:
        walk(root_id, [])
    return mapping


def _related_block(
    page: WikiPage,
    workspace: Path,
    relative_lookup: dict[str, Path],
    pages_by_id: dict[str, WikiPage],
    current_file: Path,
) -> list[str]:
    if not page.relatedPages:
        return []

    entries: list[str] = []
    for related_id in page.relatedPages:
        target_rel = relative_lookup.get(related_id)
        if not target_rel:
            continue
        target_page = pages_by_id.get(related_id)
        if not target_page:
            continue
        target_path = (workspace / target_rel).resolve()
        rel_link = os.path.relpath(target_path, start=current_file.parent.resolve())
        entries.append(f"- [{target_page.title}]({rel_link})")

    if not entries:
        return []

    return [
        RELATED_START,
        "## Related Pages",
        "",
        *entries,
        RELATED_END,
        "",
    ]


def _single_related_block(
    page: WikiPage,
    anchor_lookup: dict[str, str],
    pages_by_id: dict[str, WikiPage],
) -> list[str]:
    links = []
    for related_id in page.relatedPages:
        anchor = anchor_lookup.get(related_id)
        if not anchor:
            continue
        related_page = pages_by_id.get(related_id)
        related_title = related_page.title if related_page else related_id
        links.append(f"[{related_title}]({anchor})")

    if not links:
        return []

    display_links = ", ".join(links)
    return [RELATED_START, f"> Related pages: {display_links}", RELATED_END, ""]


def export_markdown_workspace(
    *,
    pages: list[WikiPage],
    structure: WikiStructureModel,
    manifest: ExportManifest,
) -> ExportManifest:
    """Write markdown files (single or multi) and persist manifest metadata."""
    workspace = manifest.root_path
    workspace.mkdir(parents=True, exist_ok=True)

    pages_by_id = {page.id: page for page in pages}

    if manifest.layout == "multi":
        section_map = _build_section_paths(structure)
        relative_lookup: dict[str, Path] = {}
        for page in pages:
            section_parts = section_map.get(page.id, [])
            section_path = Path(
                *[slugify(part) for part in section_parts if slugify(part)],
            )
            filename = f"{slugify(page.title or page.id)}.md"
            relative_lookup[page.id] = section_path / filename

        exported_pages: list[ExportedPage] = []
        for page in pages:
            relative_path = relative_lookup[page.id]
            file_path = (workspace / relative_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            lines = [
                encode_marker(page.id, page.title),
                "",
                f"# {page.title}",
                "",
                page.content.strip(),
                "",
            ]
            lines.extend(
                _related_block(
                    page,
                    workspace.resolve(),
                    relative_lookup,
                    pages_by_id,
                    file_path,
                ),
            )

            file_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
            exported_pages.append(
                ExportedPage(
                    id=page.id,
                    title=page.title,
                    relative_path=str(relative_path),
                ),
            )

        manifest.pages = exported_pages
        manifest.artifact = str(workspace)
        manifest.save()
        return manifest

    # single layout
    anchor_lookup = {page.id: slugify(page.id) for page in pages}
    file_path = manifest.artifact_path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        f"# Wiki Documentation for {manifest.repo_url or manifest.repo_display}",
        "",
        f"Generated on: {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "## Table of Contents",
        "",
    ]
    for page in pages:
        header.append(f"- [{page.title}](#{anchor_lookup[page.id]})")
    header.append("")

    body: list[str] = []
    exported_pages = []
    for page in pages:
        marker = encode_marker(page.id, page.title)
        body.extend(
            [
                f'<a id="{anchor_lookup[page.id]}"></a>',
                marker,
                "",
                f"## {page.title}",
                "",
                page.content.strip(),
                "",
            ],
        )
        body.extend(
            _single_related_block(
                page,
                {k: f"#{v}" for k, v in anchor_lookup.items()},
                pages_by_id,
            ),
        )
        body.extend(["---", ""])
        exported_pages.append(ExportedPage(id=page.id, title=page.title))

    file_path.write_text("\n".join(header + body).strip() + "\n", encoding="utf-8")
    manifest.pages = exported_pages
    manifest.save()
    return manifest


def _parse_multi_file(file_path: Path) -> tuple[str, str, str]:
    text = file_path.read_text(encoding="utf-8")
    match = PAGE_MARKER_PATTERN.search(text)
    if not match:
        raise ValueError(f"No DeepWiki marker found in {file_path}")
    payload = decode_marker(match.group("payload"))
    body = text[match.end() :].lstrip()
    cleaned = _strip_generated_blocks(body)
    title, content = _split_title(cleaned, payload.get("title", ""))
    return payload["page_id"], title, content


def _parse_single_file(
    file_path: Path,
    expected_ids: Iterable[str],
) -> dict[str, tuple[str, str]]:
    text = file_path.read_text(encoding="utf-8")
    matches = list(PAGE_MARKER_PATTERN.finditer(text))
    updates: dict[str, tuple[str, str]] = {}

    for idx, match in enumerate(matches):
        payload = decode_marker(match.group("payload"))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        segment = text[start:end].lstrip()
        cleaned = _strip_generated_blocks(segment)
        title, content = _split_title(cleaned, payload.get("title", ""))
        updates[payload["page_id"]] = (title, content)

    missing = [page_id for page_id in expected_ids if page_id not in updates]
    if missing:
        raise ValueError(f"Missing page blocks for: {', '.join(missing)}")
    return updates


def sync_manifest(
    manifest: ExportManifest,
    *,
    changed_paths: set[Path] | None = None,
) -> dict[str, object]:
    """Apply edits from the workspace back to the cache file."""
    cache_path = Path(manifest.cache_file)
    if not cache_path.exists():
        raise FileNotFoundError(f"Cache file not found: {cache_path}")

    changed_set = {path.resolve() for path in changed_paths} if changed_paths else None
    updates: dict[str, tuple[str, str]] = {}

    if manifest.layout == "multi":
        workspace = manifest.root_path.resolve()
        for page in manifest.pages:
            if page.relative_path is None:
                continue
            file_path = (workspace / page.relative_path).resolve()
            if changed_set and file_path not in changed_set:
                continue
            page_id, title, content = _parse_multi_file(file_path)
            updates[page_id] = (title, content)
    else:
        single_path = manifest.artifact_path.resolve()
        if changed_set and single_path not in changed_set:
            return {"updated": 0, "timestamp": manifest.last_synced}
        updates = _parse_single_file(single_path, [page.id for page in manifest.pages])

    if not updates:
        return {"updated": 0, "timestamp": manifest.last_synced}

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    generated = data.get("generated_pages", {})
    structure_pages = data.get("wiki_structure", {}).get("pages", [])

    updated_count = 0
    for page_id, (title, content) in updates.items():
        if page_id not in generated:
            continue
        generated[page_id]["content"] = content
        generated[page_id]["title"] = title
        updated_count += 1
        for entry in structure_pages:
            if entry.get("id") == page_id:
                entry["title"] = title
                entry["content"] = content
                break

    timestamp = _timestamp()
    data["generated_pages"] = generated
    if "wiki_structure" in data:
        data["wiki_structure"]["pages"] = structure_pages
    data["updated_at"] = timestamp

    cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    manifest.last_synced = timestamp
    manifest.save()

    logger.info(
        "wiki_sync_applied",
        repo=manifest.repo_display,
        pages=updated_count,
        status="success",
        operation="sync",
        correlation_id=os.environ.get("CORRELATION_ID"),
    )
    return {"updated": updated_count, "timestamp": timestamp}


def list_manifests(base_dir: Path) -> list[ExportManifest]:
    """Discover manifest files underneath a workspace directory."""
    if not base_dir.exists():
        return []
    manifests: list[ExportManifest] = []
    for manifest_file in base_dir.rglob(MANIFEST_FILENAME):
        try:
            manifests.append(ExportManifest.from_path(manifest_file))
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    return sorted(manifests, key=lambda m: (m.repo_display, m.version), reverse=True)


def watch_workspace(manifest: ExportManifest):
    """Yield sync summaries whenever markdown files change."""
    targets = [path for path in manifest.watch_targets() if path.exists()]
    if not targets:
        raise FileNotFoundError(
            f"No watch targets available for workspace {manifest.root_dir}",
        )

    for changes in watch(*targets, recursive=True, debounce=750):
        changed_files = {
            Path(path).resolve()
            for change, path in changes
            if Path(path).suffix.lower() == ".md"
        }
        if not changed_files:
            continue
        yield sync_manifest(manifest, changed_paths=changed_files)


